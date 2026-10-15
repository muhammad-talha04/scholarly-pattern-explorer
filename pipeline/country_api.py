"""Read-side helpers for the /countries routes. core.py calls these."""
from __future__ import annotations
import json
from functools import lru_cache
from pathlib import Path

from ml.paths import country_snapshot

# Anchored to the repo root (ml/paths.py). Absolute COUNTRY_SNAPSHOT values are kept.
SNAPSHOT = country_snapshot()


@lru_cache(maxsize=8)
def _load(path: str, mtime: float) -> dict:
    return json.loads(Path(path).read_text())


def snapshot() -> dict:
    if not SNAPSHOT.exists():
        return {}
    return _load(str(SNAPSHOT.resolve()), SNAPSHOT.stat().st_mtime_ns)


def _year_rows(tally: dict, code: str) -> list[dict]:
    whole = (tally.get("by_year") or {}).get(code) or {}
    frac = (tally.get("frac") or {}).get(code) or {}
    rows = []
    for year in sorted(set(whole) | set(frac), key=str):
        if not str(year).isdigit():
            continue
        rows.append({
            "year": int(year),
            "paper_count": int(whole.get(year) or 0),
            "fractional_count": float(frac.get(year) or 0),
        })
    return rows


def countries(counting: str = "fractional") -> list[dict]:
    s = snapshot()
    rows = s.get("countries_full" if counting == "full" else "countries", [])
    tally = s.get("tally") or {}
    out = []
    for r in rows:
        code = r["code"]
        years = _year_rows(tally, code)
        whole = (tally.get("by_year") or {}).get(code) or {}
        frac = (tally.get("frac") or {}).get(code) or {}
        out.append({
            "code": code,
            "name": r["name"],
            "papers": r["papers"],
            "growth_pct": r["growth_pct"],
            "top_topics": r["top_topics"],
            "counting": r["counting"],
            "paper_count": sum(int(v) for v in whole.values()),
            "fractional_count": round(sum(float(v) for v in frac.values()), 6),
            "by_year": years,
        })
    return out


def country(code: str, counting: str = "fractional") -> dict | None:
    return next((r for r in countries(counting) if r["code"] == code.upper()), None)


def collaborations(counting: str = "fractional", limit: int = 200) -> list[dict]:
    """counting: 'fractional' (default, each paper sums to 1), 'per_country' (1/n per pair), or 'full'."""
    key = {"full": "collaborations_full", "per_country": "collaborations_1n"}.get(counting, "collaborations")
    return snapshot().get(key, [])[:limit]


# A globe or streamgraph page is a few thousand cells. 10000 covers a filtered
# slice of the free OpenAlex corpus without letting one call dump the whole table.
TOPIC_COUNTRY_YEAR_DEFAULT_LIMIT = 1000
TOPIC_COUNTRY_YEAR_MAX_LIMIT = 10_000


def clamp_topic_country_year_limit(limit: int) -> int:
    """Same rule as /search and /related: below 1 becomes 1, above the max is capped."""
    return max(1, min(int(limit), TOPIC_COUNTRY_YEAR_MAX_LIMIT))


def topic_country_years(topic_id: str | None = None, country: str | None = None,
                        year: int | None = None,
                        limit: int = TOPIC_COUNTRY_YEAR_DEFAULT_LIMIT) -> list[dict]:
    """Rows of topic_id, topic_name, country_code, year, paper_count, fractional_count.

    `limit` defaults to 1000 and is clamped to 1..10000.
    """
    rows = snapshot().get("topic_country_year") or []
    if topic_id:
        rows = [r for r in rows if r.get("topic_id") == topic_id]
    if country:
        code = country.upper()
        rows = [r for r in rows if r.get("country_code") == code]
    if year is not None:
        rows = [r for r in rows if r.get("year") == year]
    return rows[:clamp_topic_country_year_limit(limit)]
