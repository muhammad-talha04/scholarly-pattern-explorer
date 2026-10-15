"""Repo-root-anchored data paths, so the API works no matter which directory it is started from."""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def resolve(p: str | Path) -> Path:
    """Absolute paths are kept; relative ones are taken from the repo root, not the CWD."""
    p = Path(p)
    return p if p.is_absolute() else REPO_ROOT / p


def ml_data_dir() -> Path:
    return resolve(os.getenv("ML_DATA_DIR", "data/ml"))


def discoveries_path() -> Path:
    """Latest precomputed gaps, emerging topics, and similar papers.

    ``DISCOVERIES_PATH`` overrides the file. Otherwise it sits in the ML data dir
    so a test can point ``ML_DATA_DIR`` at a temp folder and isolate the snapshot.
    """
    env = os.getenv("DISCOVERIES_PATH")
    if env:
        return resolve(env)
    return ml_data_dir() / "discoveries.json"


def country_snapshot() -> Path:
    return resolve(os.getenv("COUNTRY_SNAPSHOT", "data/country_snapshot.json"))


def topic_country_year_db() -> Path:
    """SQLite aggregate written by pipeline/country_stats.py. Same anchoring as the snapshot."""
    return resolve(os.getenv("TOPIC_COUNTRY_YEAR_DB", "data/topic_country_year.sqlite"))
