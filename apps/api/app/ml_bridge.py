"""Glue between the API contract (schemas.py) and the ML package at repo root (ml/)."""
from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.cs_topics import is_cs  # noqa: E402
from ml.emerging import load_topic_rows, rank_emerging  # noqa: E402
from ml.gaps import explain_growth_gap, find_gaps, load_inputs  # noqa: E402
from ml.incremental import IncrementalMiner  # noqa: E402
from ml.paths import country_snapshot, ml_data_dir  # noqa: E402
from ml.research_gaps import examples_for_topics, examples_from_works, semantic_gaps_from_store  # noqa: E402
from ml.service import MLService  # noqa: E402
from ml.text import sentences  # noqa: E402


def data_dir() -> Path:
    return ml_data_dir()


@lru_cache(maxsize=1)
def get_service() -> MLService:
    return MLService()


@lru_cache(maxsize=1)
def get_miner() -> IncrementalMiner:
    return IncrementalMiner(data_dir() / "patterns")


def one_line(summary: str | None) -> str | None:
    if not summary:
        return None
    s = sentences(summary)
    return s[0] if s else summary


def snapshot_path() -> Path:
    return country_snapshot()


def get_gaps(limit: int = 20) -> list[dict]:
    """Snapshot `topic_year_counts` if present, else computed from data/works_v2.jsonl."""
    tyc, top, _src = load_inputs(snapshot_path())
    rows = [g for g in find_gaps(tyc, top, limit=limit * 20) if is_cs(g.get("topic") or "")]
    return rows[:limit]


def _snapshot_semantic_gaps() -> list[dict] | None:
    """semantic_gaps from the newest discoveries-<date>.json, or None when there is none."""
    import json
    files = sorted((data_dir() / "snapshots").glob("discoveries-*.json"))
    if not files:
        return None
    try:
        rows = json.loads(files[-1].read_text()).get("semantic_gaps")
    except (OSError, ValueError):
        return None
    return rows if isinstance(rows, list) else None


def get_semantic_gaps(limit: int = 10) -> list[dict]:
    """Topic pairs and thin regions in the embedding index.

    Reads the precomputed discoveries snapshot when one exists: computing it live
    loads every vector, which runs a 512 MB free instance out of memory on a
    large index. Falls back to the live computation. Empty if nothing is indexed.
    """
    cached = _snapshot_semantic_gaps()
    if cached is not None:
        keep = [g for g in cached if all(is_cs(str(t)) for t in (g.get("items") or []))]
        return keep[:limit]
    try:
        store = get_service().store
    except Exception:
        return []
    return semantic_gaps_from_store(store, limit=limit)


def get_emerging(country: str | None = None, limit: int = 20) -> list[dict]:
    """Topics ranked by smoothed year-over-year growth. Optional ISO country code."""
    rows, _src = load_topic_rows()
    return rank_emerging(rows, country=country, limit=limit)


def gap_examples(topics: list[str], n: int = 3) -> list[dict]:
    found = examples_for_topics(get_service().store, topics, n=n)
    return found or examples_from_works(topics, n=n)


def growth_explanation(gap: dict) -> str:
    return explain_growth_gap(gap)
