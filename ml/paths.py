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
    """SQLite topic × country × year file used when Postgres is not selected."""
    return resolve(os.getenv("TOPIC_COUNTRY_YEAR_DB", "data/topic_country_year.sqlite"))


def use_postgres() -> bool:
    """Same backend choice as ``ml.store.get_store``.

    ``ML_VECTOR_BACKEND=local`` keeps files even when ``DATABASE_URL`` is set.
    ``ML_VECTOR_BACKEND=pgvector`` selects Postgres and needs ``DATABASE_URL``.
    When the variable is unset, a ``DATABASE_URL`` selects Postgres.
    """
    backend = os.getenv("ML_VECTOR_BACKEND", "").strip().lower()
    if backend == "local":
        return False
    if backend == "pgvector":
        return True
    return bool(os.getenv("DATABASE_URL"))
