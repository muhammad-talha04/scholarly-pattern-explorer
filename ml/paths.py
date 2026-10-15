"""Repo-root-anchored data paths, so the API works no matter which directory it is started from."""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def resolve(p: str | Path) -> Path:
    """Absolute paths are kept; relative ones are taken from the repo root, not the CWD."""
    p = Path(p)
    return p if p.is_absolute() else REPO_ROOT / p


# Committed snapshots built from the live corpus (see docs/STATUS.md). Used only when
# the env var is unset and the regular data/ file is missing, e.g. on a fresh deploy
# whose disk is ephemeral.
DEPLOY_DATA = REPO_ROOT / "deploy" / "data"


def _with_fallback(env: str, default: str, deployed: Path) -> Path:
    raw = os.getenv(env)
    if raw:
        return resolve(raw)
    p = resolve(default)
    if not p.exists() and deployed.exists() and os.getenv("SPE_DEPLOY_SNAPSHOTS", "1") != "0":
        return deployed
    return p


def ml_data_dir() -> Path:
    return _with_fallback("ML_DATA_DIR", "data/ml", DEPLOY_DATA / "ml")


def country_snapshot() -> Path:
    return _with_fallback("COUNTRY_SNAPSHOT", "data/country_snapshot.json",
                          DEPLOY_DATA / "country_snapshot.json")


def topic_country_year_db() -> Path:
    """SQLite aggregate written by pipeline/country_stats.py. Same anchoring as the snapshot."""
    return resolve(os.getenv("TOPIC_COUNTRY_YEAR_DB", "data/topic_country_year.sqlite"))
