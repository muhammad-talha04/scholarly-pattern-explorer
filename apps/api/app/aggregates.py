"""Chart totals for GET /aggregates/* (contract: PR #57).

One GROUP BY over paper_embeddings.meta (``store.aggregate_counts()``) plus the
sampling_rates table, held in a process cache for ``AGGREGATES_TTL_SECONDS``
(default 300). After a load the totals refresh on their own: the first request
after the TTL gets the cached totals and triggers one background rescan, so the
next request sees the new numbers. No migration, materialized view or manual step.
The scan reads every row's meta once (~3.5 s at 26.5k rows on Supabase free tier,
~10 s projected at 80k), which is why it never runs on a warm request.

estimated_total for a month is ``sampling_rates.openalex_total`` as stored: that
column already is the OpenAlex population for the month (``meta.count`` of the
filtered query), so no scaling is applied. A year's estimate is the sum of its
months, and null unless every month of that year that has papers has a row.
"""
from __future__ import annotations

import logging
import os
import threading
import time

from . import ml_bridge as ml

OTHER = "Other"
_lock = threading.Lock()
_first = threading.Lock()          # single-flight cold load
_refreshing = threading.Lock()     # at most one background rescan
_cache: dict = {"at": None, "data": None}


def ttl_seconds() -> float:
    try:
        return max(0.0, float(os.getenv("AGGREGATES_TTL_SECONDS", "300")))
    except ValueError:
        return 300.0


def clear_cache() -> None:
    with _lock:
        _cache["at"], _cache["data"] = None, None


def _load() -> dict:
    store = ml.get_service().store
    counts = store.aggregate_counts()
    rates = {}
    for month, r in (store.sampling_rates() or {}).items():
        try:
            rates[str(month)[:7]] = int(r["openalex_total"])
        except (KeyError, TypeError, ValueError):
            continue
    return {"papers": counts["papers"], "topics": counts["topics"], "rates": rates}


def _refresh() -> dict:
    fresh = _load()
    with _lock:
        _cache["at"], _cache["data"] = time.monotonic(), fresh
    return fresh


def _background_refresh() -> None:
    try:
        _refresh()
    except Exception:  # keep serving the stale totals; the next stale read retries
        logging.getLogger("spe.aggregates").exception("aggregates refresh failed")
    finally:
        _refreshing.release()


def data() -> dict:
    """Cached aggregate inputs (stale-while-revalidate).

    First call scans synchronously (single-flight). After that a request never
    waits on the scan: once the TTL has passed, it returns the cached totals and
    one background thread rescans.
    """
    with _lock:
        cached, at = _cache["data"], _cache["at"]
    if cached is None:
        with _first:
            with _lock:
                if _cache["data"] is not None:
                    return _cache["data"]
            return _refresh()
    if time.monotonic() - at >= ttl_seconds() and _refreshing.acquire(blocking=False):
        if os.getenv("AGGREGATES_SYNC_REFRESH"):   # tests: refresh inline
            try:
                return _refresh()
            finally:
                _refreshing.release()
        threading.Thread(target=_background_refresh, daemon=True).start()
    return cached


def _keys(d: dict, grain: str, year: int | None) -> list[str]:
    if grain == "month":
        return [f"{year:04d}-{m:02d}" for m in range(1, 13)]
    years = sorted({y for (y, _m) in d["papers"]})
    return [str(y) for y in range(years[0], years[-1] + 1)] if years else []


def _bucket_of(y: int, m: str | None, grain: str, year: int | None) -> str | None:
    if grain == "year":
        return str(y)
    return m if (y == year and m) else None


def periods(d: dict, grain: str, year: int | None) -> list[dict]:
    keys = _keys(d, grain, year)
    sampled = dict.fromkeys(keys, 0)
    for (y, m), n in d["papers"].items():
        k = _bucket_of(y, m, grain, year)
        if k in sampled:
            sampled[k] += n
    rates = d["rates"]
    out = []
    for k in keys:
        if grain == "month":
            est = rates.get(k)
        else:
            months = [f"{k}-{i:02d}" for i in range(1, 13)]
            held = {m for (y, m) in d["papers"] if str(y) == k and m}
            known = [rates[m] for m in months if m in rates]
            est = sum(known) if known and all(m in rates for m in held) else None
        out.append({"key": k, "sampled": sampled[k], "estimated_total": est})
    return out


def publications(grain: str, year: int | None) -> dict:
    d = data()
    buckets = [{"key": p["key"], "paper_count": p["sampled"], **p} for p in periods(d, grain, year)]
    return {"grain": grain, "year": year if grain == "month" else None,
            "total": sum(b["paper_count"] for b in buckets), "buckets": buckets}


def topics(grain: str, year: int | None, top: int) -> dict:
    d = data()
    keys = _keys(d, grain, year)
    idx = set(keys)
    per: dict[str, dict[str, float]] = {}
    for (y, m, t), v in d["topics"].items():
        k = _bucket_of(y, m, grain, year)
        if k in idx:
            row = per.setdefault(t, {})
            row[k] = row.get(k, 0.0) + v
    ranked = sorted(per, key=lambda t: (-sum(per[t].values()), t))
    head, tail = ranked[:top], ranked[top:]
    series = [{"name": t, "points": [{"key": k, "value": round(per[t].get(k, 0.0), 6)} for k in keys]}
              for t in head]
    if tail:
        series.append({"name": OTHER, "points": [
            {"key": k, "value": round(sum(per[t].get(k, 0.0) for t in tail), 6)} for k in keys]})
    return {"grain": grain, "year": year if grain == "month" else None, "top": top,
            "series": series, "period": periods(d, grain, year)}


def countries(rows: list[dict], counting: str, year: int | None, top: int) -> dict:
    items = []
    for r in rows:
        if year is None:
            papers = float(r["papers"])
        else:
            y = next((b for b in r.get("by_year") or [] if b["year"] == year), None)
            if y is None:
                continue
            papers = float(y["fractional_count"] if counting == "fractional" else y["paper_count"])
        if papers:
            items.append({"code": r["code"], "name": r["name"], "papers": round(papers, 6)})
    items.sort(key=lambda r: (-r["papers"], r["code"]))
    head, tail = items[:top], items[top:]
    other = {"papers": round(sum(r["papers"] for r in tail), 6), "countries": len(tail)} if tail else None
    d = data()
    per = periods(d, "year", None)
    if year is not None:
        per = [p for p in per if p["key"] == str(year)] or [{"key": str(year), "sampled": 0,
                                                              "estimated_total": None}]
    total = sum(p["sampled"] for p in per)
    return {"counting": counting, "year": year, "top": top, "total": total,
            "items": head, "other": other, "period": per}
