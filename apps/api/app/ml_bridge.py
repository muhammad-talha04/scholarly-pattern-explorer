"""Glue between the API contract (schemas.py) and the ML package at repo root (ml/)."""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.discovery_store import load_discoveries as _load_discoveries  # noqa: E402
from ml.gaps import explain_growth_gap  # noqa: E402
from ml.incremental import IncrementalMiner  # noqa: E402
from ml.paths import ml_data_dir  # noqa: E402
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


def load_discoveries() -> dict | None:
    """Latest precomputed gaps, emerging topics, and similar papers.

    ``None`` means ``discover`` has not run yet. Callers filter this dict; they
    do not recompute it. The read and write live in ``ml.discovery_store`` so
    they can move onto the shared store later.
    """
    return _load_discoveries()


def growth_explanation(gap: dict) -> str:
    return explain_growth_gap(gap)
