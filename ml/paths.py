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


def topic_country_year_db() -> Path:
    """SQLite aggregate from PR #6: topic_id, topic_name, country_code, year, paper_count, fractional_count.

    Defaults to the file written beside the country snapshot (`data/topic_country_year.sqlite`).
    """
    env = os.getenv("TOPIC_COUNTRY_YEAR_DB")
    if env:
        return resolve(env)
    return country_snapshot().with_name("topic_country_year.sqlite")
