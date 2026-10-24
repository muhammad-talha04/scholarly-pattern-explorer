"""Twice-monthly snapshot of emerging topics and embedding-space gaps.

Reads the incremental stores (topic table or works JSONL, plus the vector index).
Does not rebuild embeddings or patterns. Also records an ``emerging_score`` in
``[0, 1]`` for each galaxy colour.
"""
from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path

from .emerging import load_topic_rows, rank_emerging
from .paths import ml_data_dir
from .research_gaps import semantic_gaps_from_store


def _growth_by_topic(emerging: list[dict]) -> dict[str, float]:
    out: dict[str, float] = {}
    for row in emerging or []:
        if not isinstance(row, dict):
            continue
        raw = row.get("growth_score", row.get("growth_rate"))
        try:
            score = float(raw)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(score) or score <= 0:
            continue
        for key in (row.get("topic_name"), row.get("topic"), row.get("topic_id")):
            if key is None:
                continue
            text = str(key).strip()
            if text:
                out[text] = max(out.get(text, 0.0), score)
    return out


def cluster_emerging_scores(emerging: list[dict], papers: list[dict]) -> dict[str, float]:
    """Emerging strength of each galaxy colour, scaled to ``[0, 1]``.

    A paper's score is the highest emerging-topic growth among its topics.
    A colour's raw score is the mean of its papers. Scores are then divided
    by the hottest colour, so the busiest emerging colour is 1 and a colour
    with no emerging topic is 0. Keys are ``color_index`` (as strings).
    ``cluster_id`` is not used. Unclustered papers (``color_index < 0``) are
    left out.
    """
    growth = _growth_by_topic(emerging)
    grouped: dict[int, list[float]] = {}
    for paper in papers or []:
        if not isinstance(paper, dict):
            continue
        try:
            color = int(paper.get("color_index"))
        except (TypeError, ValueError):
            continue
        if color < 0:
            continue
        paper_score = 0.0
        for topic in paper.get("topics") or []:
            if not isinstance(topic, str):
                continue
            paper_score = max(paper_score, growth.get(topic.strip(), 0.0))
        grouped.setdefault(color, []).append(paper_score)
    if not grouped:
        return {}
    means = {color: sum(values) / len(values) for color, values in grouped.items()}
    peak = max(means.values())
    scores = {}
    for color, raw in means.items():
        scaled = 0.0 if peak <= 0 else raw / peak
        if not math.isfinite(scaled):
            scaled = 0.0
        scores[str(color)] = round(min(1.0, max(0.0, scaled)), 4)
    return scores


def _papers_for_scores(store) -> list[dict]:
    """Papers already placed in the galaxy, with the topics stored on each vector."""
    if store is None or not hasattr(store, "get_document"):
        return []
    graph = store.get_document("galaxy") or {}
    nodes = graph.get("nodes") or []
    topics_of: dict[str, list[str]] = {}
    if hasattr(store, "rows"):
        ids, _, metas = store.rows()
        for wid, meta in zip(ids, metas):
            meta = meta if isinstance(meta, dict) else {}
            topics_of[str(wid)] = [t for t in (meta.get("topics") or []) if isinstance(t, str) and t]
    papers = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        wid = str(node.get("id") or "")
        papers.append({"color_index": node.get("color_index"), "topics": topics_of.get(wid, [])})
    return papers


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def latest_discoveries() -> dict | None:
    """Newest snapshot: ``discoveries.json``, else the latest dated file."""
    data = _read_json(ml_data_dir() / "discoveries.json")
    if data is not None:
        return data
    folder = ml_data_dir() / "snapshots"
    if not folder.is_dir():
        return None
    for path in sorted(folder.glob("discoveries-*.json"), reverse=True):
        data = _read_json(path)
        if data is not None:
            return data
    return None


def load_emerging_scores() -> dict[str, float]:
    """``color_index`` -> score in ``[0, 1]`` from the latest discoveries snapshot."""
    raw = (latest_discoveries() or {}).get("emerging_scores") or {}
    if not isinstance(raw, dict):
        return {}
    out = {}
    for key, value in raw.items():
        try:
            color = str(int(key))
            score = float(value)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(score):
            continue
        out[color] = round(min(1.0, max(0.0, score)), 4)
    return out


def refresh_discoveries(run_date: str | None = None, *,
                        store=None, snapshot_path=None, db_path=None,
                        works_path=None, cs_only: bool = True) -> dict:
    """Write ``data/ml/snapshots/discoveries-<date>.json`` and return a short summary."""
    run_date = run_date or date.today().isoformat()
    rows, source = load_topic_rows(snapshot_path, db_path, works_path)
    emerging = rank_emerging(rows, cs_only=cs_only)
    if store is None:
        from .store import get_store
        store = get_store()
    gaps = semantic_gaps_from_store(store, cs_only=cs_only)
    scores = cluster_emerging_scores(emerging, _papers_for_scores(store))
    payload = {"date": run_date, "topic_source": source,
               "n_emerging": len(emerging), "n_semantic_gaps": len(gaps),
               "emerging": emerging, "semantic_gaps": gaps,
               "emerging_scores": scores}
    body = json.dumps(payload)
    out = ml_data_dir() / "snapshots" / f"discoveries-{run_date}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")
    latest = ml_data_dir() / "discoveries.json"
    latest.parent.mkdir(parents=True, exist_ok=True)
    latest.write_text(body, encoding="utf-8")
    return {"date": run_date, "topic_source": source, "path": str(out),
            "n_emerging": len(emerging), "n_semantic_gaps": len(gaps)}
