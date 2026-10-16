"""Equal-period growth metric (docs/growth_spec.md)."""
import json
import statistics
from pathlib import Path

import pytest

from pipeline.country_stats import combine, snapshot, tally

SNAP = Path(__file__).resolve().parents[2] / "deploy" / "data" / "country_snapshot.json"


def _works(code, n, date, other=None):
    return [{"id": f"{code}{date}{i}", "year": int(date[:4]), "date": date,
             "countries": [code] + ([other] if other else []), "topics": ["AI"]} for i in range(n)]


def _row(snap, code, key="countries"):
    return next(r for r in snap[key] if r["code"] == code)


def test_equal_periods_cut_at_newest_paper():
    # previous year: 40 inside Jan 1..Mar 10, 500 after Mar 10 (must be ignored)
    works = (_works("PK", 40, "2025-02-01") + _works("PK", 500, "2025-11-01")
             + _works("PK", 60, "2026-03-10"))
    r = _row(snapshot(tally(works)), "PK")
    assert r["growth_window_start"] == "2026-01-01" and r["growth_window_end"] == "2026-03-10"
    assert r["growth_cur_count"] == 60 and r["growth_prev_count"] == 40
    assert r["growth_pct"] == 50.0 and r["growth_reason"] is None


def test_too_few_papers_in_either_period():
    works = _works("IS", 29, "2025-01-05") + _works("IS", 400, "2026-01-05")
    r = _row(snapshot(tally(works)), "IS")
    assert r["growth_pct"] is None and r["growth_reason"] == "too_few_papers"
    assert r["growth_cur_count"] == 400 and r["growth_prev_count"] == 29


def test_fractional_mode_uses_shares_for_threshold():
    # 50 papers each period, all shared with another country -> 25 fractional each
    works = _works("PK", 50, "2025-01-05", "US") + _works("PK", 50, "2026-01-05", "US")
    snap = snapshot(tally(works))
    assert _row(snap, "PK")["growth_reason"] == "too_few_papers"
    full = _row(snap, "PK", "countries_full")
    assert full["growth_pct"] == 0.0 and full["growth_reason"] is None


def test_window_touching_2024_is_hidden():
    works = _works("CN", 100, "2024-11-01") + _works("CN", 100, "2025-06-01")
    r = _row(snapshot(tally(works)), "CN")
    assert r["growth_pct"] is None and r["growth_reason"] == "partial_year"


def test_date_counters_combine_incrementally():
    a, b = _works("PK", 40, "2025-02-01"), _works("PK", 45, "2026-02-01")
    inc = snapshot(combine(json.loads(json.dumps(tally(a))), tally(b)))
    assert inc["countries"] == snapshot(tally(a + b))["countries"]


def _median_shown(rows):
    shown = [r["growth_pct"] for r in rows if r["growth_pct"] is not None]
    return statistics.median(shown) if shown else None


def test_median_growth_sanity_on_steady_corpus():
    """Council kill criterion: steady output must not show a median below -50%."""
    works = []
    for code in ("CN", "US", "IN", "GB"):
        for y in (2025, 2026):
            for m in range(1, 10):
                works += _works(code, 10, f"{y}-{m:02d}-15")
    assert _median_shown(snapshot(tally(works))["countries"]) >= -50


@pytest.mark.xfail(strict=True, reason=(
    "Committed corpus is front-loaded: monthly paper counts fall from ~2,000 (Jan 2025) to "
    "<30 (mid 2026), so 2026 YTD is ~85% below the same dates in 2025. This is a sampling "
    "problem in ingest, not year bucketing. Remove xfail once the corpus is re-sampled."))
def test_committed_snapshot_median_growth_not_below_minus_50():
    snap = json.loads(SNAP.read_text())
    med = _median_shown(snap["countries"])
    assert med is None or med >= -50


def test_share_of_corpus_same_window_and_rules():
    # 2025 window: PK 40 of 200 papers (20%); 2026 window: PK 60 of 200 (30%)
    works = (_works("PK", 40, "2025-02-01") + _works("US", 160, "2025-02-01")
             + _works("PK", 500, "2025-11-01")                     # outside the window
             + _works("PK", 60, "2026-03-10") + _works("US", 140, "2026-03-10"))
    snap = snapshot(tally(works))
    pk, us = _row(snap, "PK"), _row(snap, "US")
    assert (pk["share_pct"], pk["share_prev_pct"], pk["share_change_pp"]) == (30.0, 20.0, 10.0)
    assert pk["share_reason"] is None and us["share_change_pp"] == -10.0
    few = snapshot(tally(_works("IS", 29, "2025-01-05") + _works("IS", 40, "2026-01-05")))
    assert _row(few, "IS")["share_reason"] == "too_few_papers" and _row(few, "IS")["share_pct"] is None
    old = snapshot(tally(_works("CN", 100, "2024-11-01") + _works("CN", 100, "2025-06-01")))
    assert _row(old, "CN")["share_reason"] == "partial_year"


def test_share_fractional_shares_sum_to_100():
    works = []
    for d in ("2025-03-01", "2026-03-01"):
        works += _works("PK", 80, d, "US") + _works("US", 40, d) + _works("DE", 60, d)
    rows = [r for r in snapshot(tally(works))["countries"] if r["share_pct"] is not None]
    assert abs(sum(r["share_pct"] for r in rows) - 100) < 0.05
