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


def country_snapshot() -> Path:
    return resolve(os.getenv("COUNTRY_SNAPSHOT", "data/country_snapshot.json"))
