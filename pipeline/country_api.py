"""Read-side helpers for the /countries routes. core.py calls these."""
from __future__ import annotations
import json, os
from functools import lru_cache
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_env = Path(os.environ.get("COUNTRY_SNAPSHOT", "data/country_snapshot.json"))
# Anchored to the repo root so the API finds the snapshot whatever its working directory.
SNAPSHOT = _env if _env.is_absolute() else _ROOT / _env


@lru_cache(maxsize=1)
def _load(mtime: float) -> dict:
    return json.loads(SNAPSHOT.read_text())


def snapshot() -> dict:
    if not SNAPSHOT.exists():
        return {}
    return _load(SNAPSHOT.stat().st_mtime)


def countries(counting: str = "fractional") -> list[dict]:
    s = snapshot()
    rows = s.get("countries_full" if counting == "full" else "countries", [])
    return [{k: r[k] for k in ("code", "name", "papers", "growth_pct", "top_topics", "counting")} for r in rows]


def country(code: str, counting: str = "fractional") -> dict | None:
    return next((r for r in countries(counting) if r["code"] == code.upper()), None)


def collaborations(counting: str = "fractional", limit: int = 200) -> list[dict]:
    """counting: 'fractional' (default, each paper sums to 1), 'per_country' (1/n per pair), or 'full'."""
    key = {"full": "collaborations_full", "per_country": "collaborations_1n"}.get(counting, "collaborations")
    return snapshot().get(key, [])[:limit]
