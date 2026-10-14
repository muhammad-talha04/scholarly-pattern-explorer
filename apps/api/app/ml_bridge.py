"""Glue between the API contract (schemas.py) and the ML package at repo root (ml/)."""
from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.gaps import find_gaps, load_inputs  # noqa: E402
from ml.incremental import IncrementalMiner  # noqa: E402
from ml.service import MLService  # noqa: E402
from ml.text import sentences  # noqa: E402


def data_dir() -> Path:
    return Path(os.getenv("ML_DATA_DIR", str(ROOT / "data" / "ml")))


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
    return Path(os.getenv("COUNTRY_SNAPSHOT", str(ROOT / "data" / "country_snapshot.json")))


def get_gaps(limit: int = 20) -> list[dict]:
    """Snapshot `topic_year_counts` if present, else computed from data/works_v2.jsonl."""
    tyc, top, _src = load_inputs(snapshot_path())
    return find_gaps(tyc, top, limit=limit)
