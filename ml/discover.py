"""Twice-monthly snapshot of gaps, emerging topics, and similar papers.

This is the only place that scans the vector index or the topic table for
those features. The API reads the file written here.
"""
from __future__ import annotations

from datetime import date

import numpy as np

from .discovery_store import save_discoveries
from .emerging import load_topic_rows, rank_emerging
from .gaps import explain_growth_gap, find_gaps, load_inputs
from .research_gaps import examples_for_topics, examples_from_works, semantic_gaps_from_store

SIMILAR_K = 10


def _neighbor(wid: str, score: float, meta: dict | None) -> dict:
    meta = meta or {}
    return {"work_id": wid, "title": meta.get("title") or "", "pub_year": meta.get("pub_year"),
            "score": round(float(score), 4), "topics": list(meta.get("topics") or []),
            "authors": list(meta.get("authors") or []), "countries": list(meta.get("countries") or []),
            "cited_by": meta.get("cited_by") or 0}


def precompute_similar(store, k: int = SIMILAR_K) -> dict:
    """Top-k neighbours for every indexed paper, one batched multiply.

    The request path looks these up. It does not call ``store.search``.
    """
    if store is None or len(store) == 0 or not hasattr(store, "rows"):
        return {}
    ids, vecs, metas = store.rows()
    ids = list(ids)
    n = len(ids)
    if n == 0:
        return {}
    mat = np.asarray(vecs, dtype=np.float32)
    if mat.ndim != 2 or mat.shape[0] != n:
        return {}
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    mat = mat / norms
    k_eff = min(k, n - 1)
    out: dict[str, list[dict]] = {}
    for start in range(0, n, 256):
        block = mat[start:start + 256] @ mat.T
        for offset, row in enumerate(block):
            idx = start + offset
            if k_eff <= 0:
                out[ids[idx]] = []
                continue
            scores = np.array(row, dtype=np.float32, copy=True)
            scores[idx] = -np.inf
            top = np.argpartition(scores, -k_eff)[-k_eff:]
            top = top[np.argsort(-scores[top])]
            out[ids[idx]] = [_neighbor(ids[j], scores[j], metas[j])
                             for j in top if np.isfinite(scores[j])]
    return out


def _growth_gaps(store, snapshot_path, works_path, last_year) -> list[dict]:
    tyc, top, _src = load_inputs(snapshot_path, works_path)
    gaps = find_gaps(tyc, top, last_year=last_year)
    out = []
    for gap in gaps:
        row = dict(gap)
        row["kind"] = "growth"
        row["items"] = [row["topic"]]
        row["explanation"] = explain_growth_gap(row)
        topics = row["items"]
        examples = examples_for_topics(store, topics) if store is not None else []
        row["example_papers"] = examples or examples_from_works(topics, works_path=works_path)
        out.append(row)
    return out


def _merge_gaps(growth: list[dict], semantic: list[dict]) -> list[dict]:
    merged = list(growth) + list(semantic)
    merged.sort(key=lambda g: (
        -float(g.get("gap_score") or 0),
        0 if g.get("kind", "growth") == "growth" else 1,
        -float(g.get("growth_rate") or 0),
        " ".join(g.get("items") or [str(g.get("topic") or "")]),
    ))
    return merged


def _with_examples(rows: list[dict], store, works_path) -> list[dict]:
    """Attach example papers while discover is running, so the API does not scan later."""
    out = []
    for row in rows:
        item = dict(row)
        if item.get("example_papers"):
            out.append(item)
            continue
        topics = [t for t in (item.get("items") or [item.get("topic_name") or item.get("topic")]) if t]
        examples = examples_for_topics(store, topics) if store is not None else []
        item["example_papers"] = examples or examples_from_works(topics, works_path=works_path)
        out.append(item)
    return out


def _emerging_by_country(rows: list[dict], last_year: int | None, store, works_path) -> dict[str, list[dict]]:
    codes = sorted({str(r.get("country_code") or "").upper() for r in rows if r.get("country_code")})
    out = {}
    for code in codes:
        ranked = rank_emerging(rows, country=code, last_year=last_year)
        if ranked:
            out[code] = _with_examples(ranked, store, works_path)
    return out


def refresh_discoveries(run_date: str | None = None, *,
                        store=None, snapshot_path=None, db_path=None,
                        works_path=None, last_year: int | None = None) -> dict:
    """Compute gaps, emerging topics, and similar papers, then save them."""
    run_date = run_date or date.today().isoformat()
    rows, source = load_topic_rows(snapshot_path, db_path, works_path)
    if store is None:
        from .store import get_store
        store = get_store()
    emerging = _with_examples(rank_emerging(rows, last_year=last_year), store, works_path)
    by_country = _emerging_by_country(rows, last_year, store, works_path)
    semantic = semantic_gaps_from_store(store) if store is not None else []
    growth = _growth_gaps(store, snapshot_path, works_path, last_year)
    similar = precompute_similar(store)
    payload = {"date": run_date, "topic_source": source,
               "n_emerging": len(emerging), "n_semantic_gaps": len(semantic),
               "gaps": _merge_gaps(growth, semantic),
               "emerging": emerging, "emerging_by_country": by_country,
               "semantic_gaps": semantic}
    # An empty index has nothing to save. Leaving the key off lets the API keep
    # answering from its own index until a run actually has vectors.
    if similar:
        payload["similar"] = similar
    out = save_discoveries(payload)
    return {"date": run_date, "topic_source": source, "path": str(out),
            "n_emerging": len(emerging), "n_semantic_gaps": len(semantic),
            "n_similar": len(similar)}
