"""Research-gap finder: topics that grow fast but are still small.

Input is deliberately simple so any producer can feed it:

    topic_year_counts   = {topic: {year: papers}}             (years may be str or int)
    topic_top_countries = {topic: [[code, share], ...]}        (optional, fractional counting)

Preferred source: the country snapshot written by pipeline/country_stats.py,
keys ``topic_year_counts`` and ``topic_top_countries`` (owner: grok, to be added).
Fallback: computed here directly from data/works_v2.jsonl.

Method (per topic, over the last ``years`` complete years, default 3):
  * smoothed YoY growth g_t = (c_t + k) / (c_{t-1} + k) - 1, clipped to [-1, cap];
  * growth = min(mean(g), median(g))  -> a one-off spike year is damped;
  * volume = papers in the window (base year + 3 growth years);
  * eligible: volume >= min_total, last year >= min_last, growth >= min_growth;
  * gap_score = percentile(growth) - percentile(volume) among topics with enough data.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from statistics import mean, median


def counts_from_works(works) -> tuple[dict, dict]:
    """Paper / dict records -> (topic_year_counts, topic_top_countries), fractional counting."""
    tyc: dict[str, Counter] = defaultdict(Counter)
    ctry: dict[str, Counter] = defaultdict(Counter)
    for w in works:
        d = w.to_dict() if hasattr(w, "to_dict") else w
        year = d.get("pub_year", d.get("year"))
        topics = [t for t in (d.get("topics") or []) if t]
        if not year or not topics:
            continue
        cs = sorted(set(d.get("countries") or []))
        for t in dict.fromkeys(topics):
            tyc[t][int(year)] += 1
            for c in cs:
                ctry[t][c] += 1 / len(cs)
    top = {t: [[c, round(v, 3)] for c, v in cnt.most_common()] for t, cnt in ctry.items()}
    return {t: dict(c) for t, c in tyc.items()}, top


def load_inputs(snapshot_path: str | Path | None = None,
                works_path: str | Path | None = None) -> tuple[dict, dict, str]:
    """Prefer ``topic_year_counts`` from the snapshot; else compute from the works JSONL."""
    if snapshot_path and Path(snapshot_path).exists():
        snap = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
        if snap.get("topic_year_counts"):
            return snap["topic_year_counts"], snap.get("topic_top_countries") or {}, "snapshot"
    from .papers import read_works
    from .papers import default_works_path
    path = works_path or default_works_path(Path(__file__).resolve().parents[1])
    if not path or not Path(path).exists():
        return {}, {}, "none"
    tyc, top = counts_from_works(read_works(path))
    return tyc, top, "works"


def _pct_rank(values: list[float]) -> list[float]:
    """Average-rank percentile in [0, 1]."""
    n = len(values)
    if n == 1:
        return [0.5]
    order = sorted(values)
    out = []
    for v in values:
        lo = order.index(v)
        hi = n - 1 - order[::-1].index(v)
        out.append(((lo + hi) / 2) / (n - 1))
    return out


def find_gaps(topic_year_counts: dict, topic_top_countries: dict | None = None, *,
              last_year: int | None = None, years: int = 3, smoothing: float = 5.0,
              cap: float = 2.0, min_total: int = 20, min_last: int = 5,
              min_growth: float = 0.10, top_n_countries: int = 5, limit: int = 20) -> list[dict]:
    """Rank research gaps. ``last_year`` defaults to the last complete calendar year."""
    last = last_year if last_year is not None else date.today().year - 1
    span = list(range(last - years, last + 1))
    rows = []
    for topic, by_year in topic_year_counts.items():
        c = {int(y): float(n) for y, n in by_year.items() if str(y).lstrip("-").isdigit()}
        series = [c.get(y, 0.0) for y in span]
        volume = sum(series)
        if volume < min_total or series[-1] < min_last:
            continue
        g = [min(cap, max(-1.0, (b + smoothing) / (a + smoothing) - 1))
             for a, b in zip(series, series[1:])]
        rows.append({"topic": topic, "growth": min(mean(g), median(g)), "volume": volume})
    if not rows:
        return []
    gp = _pct_rank([r["growth"] for r in rows])
    vp = _pct_rank([r["volume"] for r in rows])
    out = []
    for r, a, b in zip(rows, gp, vp):
        if r["growth"] < min_growth:
            continue
        score = a - b
        if len(rows) == 1:           # nothing to compare against: growth alone
            score = r["growth"]
        if score <= 0:
            continue
        top = (topic_top_countries or {}).get(r["topic"]) or []
        out.append({"topic": r["topic"], "growth_rate": round(r["growth"], 4),
                    "paper_count": int(r["volume"]), "gap_score": round(score, 4),
                    "top_countries": [str(x[0]) if isinstance(x, (list, tuple)) else str(x)
                                      for x in top[:top_n_countries]],
                    "window_start": span[0], "window_end": span[-1]})
    out.sort(key=lambda x: (-x["gap_score"], -x["growth_rate"]))
    return out[:limit]


def explain_growth_gap(gap: dict) -> str:
    """Plain-language line for a fast-growing, still-small topic."""
    topic = gap.get("topic") or "This topic"
    rate = gap.get("growth_rate")
    pace = f"{rate:.0%} a year" if isinstance(rate, (int, float)) else "year over year"
    text = (
        f"{topic} grew about {pace} from {gap.get('window_start')} to {gap.get('window_end')}. "
        f"{gap.get('paper_count')} papers were published in that window, so the literature is still small."
    )
    countries = [c for c in (gap.get("top_countries") or []) if c]
    if countries:
        text += " The countries with the most papers are " + ", ".join(countries[:3]) + "."
    return text
