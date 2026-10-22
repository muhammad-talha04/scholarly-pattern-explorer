"""Repo-root-anchored data paths, so the API works no matter which directory it is started from."""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def resolve(p: str | Path) -> Path:
    """Absolute paths are kept; relative ones are taken from the repo root, not the CWD."""
    p = Path(p)
    return p if p.is_absolute() else REPO_ROOT / p


# Committed snapshots built from the live corpus (see docs/STATUS.md). Used only on
# Render (or with SPE_DEPLOY_SNAPSHOTS=1) when the env var is unset and the regular data/ file is missing, e.g. on a fresh deploy
# whose disk is ephemeral.
DEPLOY_DATA = REPO_ROOT / "deploy" / "data"


def _deploy_snapshots_enabled() -> bool:
    """On by default on Render (it sets RENDER=true); SPE_DEPLOY_SNAPSHOTS=1/0 overrides."""
    flag = os.getenv("SPE_DEPLOY_SNAPSHOTS")
    if flag is not None:
        return flag == "1"
    return bool(os.getenv("RENDER"))


def _with_fallback(env: str, default: str, deployed: Path) -> Path:
    raw = os.getenv(env)
    if raw:
        return resolve(raw)
    p = resolve(default)
    if not p.exists() and deployed.exists() and _deploy_snapshots_enabled():
        return deployed
    return p


def ml_data_dir() -> Path:
    return _with_fallback("ML_DATA_DIR", "data/ml", DEPLOY_DATA / "ml")


def country_snapshot() -> Path:
    return _with_fallback("COUNTRY_SNAPSHOT", "data/country_snapshot.json",
                          DEPLOY_DATA / "country_snapshot.json")


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
