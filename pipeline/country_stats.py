"""Per-country and per-topic analytics, shaped like schemas.CountryStats.

Incremental: the previous snapshot's counters are combined with the new works
only, so a run never re-reads the whole corpus. Counting is fractional by
default (a 3-country paper gives each country 1/3); full counting is also kept.
"""
from __future__ import annotations
import argparse, json, sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from countries import COUNTRIES  # noqa: E402  (existing ISO table in repo root)

KEYS = ("by_year", "frac", "topics", "topic_years", "topic_countries")


def tally(works) -> dict:
    t = {k: defaultdict(Counter) for k in KEYS}
    pairs = Counter()
    for w in works:
        cs = w.get("countries") or []
        yr = str(w.get("year"))
        tops = [x for x in (w.get("topics") or [])[:3] if x]
        for c in cs:
            t["by_year"][c][yr] += 1
            t["frac"][c][yr] += 1 / len(cs)
            t["topics"][c].update(tops)
        for tp in tops:
            t["topic_years"][tp][yr] += 1
            t["topic_countries"][tp].update(cs)
        for i, a in enumerate(cs):
            for b in cs[i + 1:]:
                pairs[f"{a}-{b}"] += 1
    t["pairs"] = pairs
    return t


def combine(prev: dict | None, new: dict) -> dict:
    if not prev:
        return new
    out = {}
    for k in KEYS:
        m = defaultdict(Counter, {c: Counter(v) for c, v in (prev.get(k) or {}).items()})
        for c, cnt in new[k].items():
            m[c].update(cnt)
        out[k] = m
    out["pairs"] = Counter(prev.get("pairs") or {}) + new["pairs"]
    return out


def to_stats(t: dict, top_n: int = 5, counting: str = "fractional") -> list[dict]:
    src = t["frac"] if counting == "fractional" else t["by_year"]
    rows = []
    for code, years in src.items():
        ys = sorted((int(y), n) for y, n in years.items() if y.isdigit())
        growth = None
        if len(ys) >= 2 and ys[-2][1]:
            growth = round(100 * (ys[-1][1] - ys[-2][1]) / ys[-2][1], 1)
        rows.append({"code": code, "name": COUNTRIES.get(code, (code,))[0],
                     "papers": round(sum(years.values()), 2), "growth_pct": growth,
                     "top_topics": [n for n, _ in t["topics"][code].most_common(top_n)],
                     "counting": counting})
    return sorted(rows, key=lambda r: -r["papers"])


def snapshot(t: dict) -> dict:
    return {
        "tally": t,
        "countries": to_stats(t),
        "countries_full": to_stats(t, counting="full"),
        "collaborations": [{"source": p.split("-")[0], "target": p.split("-")[1], "papers": n}
                           for p, n in t["pairs"].most_common(200)],
        # Michal's gap finder: {topic: {year: count}} and top countries per topic
        "topic_year_counts": {tp: dict(ys) for tp, ys in t["topic_years"].items()},
        "topic_top_countries": {tp: [c for c, _ in cs.most_common(5)]
                                for tp, cs in t["topic_countries"].items()},
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--new", required=True, help="JSONL of works added this run")
    ap.add_argument("--prev", help="previous snapshot JSON")
    ap.add_argument("--out", default="data/country_snapshot.json")
    a = ap.parse_args(argv)
    with open(a.new, encoding="utf-8") as fh:
        new = tally(json.loads(l) for l in fh if l.strip())
    prev = json.loads(Path(a.prev).read_text())["tally"] if a.prev and Path(a.prev).exists() else None
    snap = snapshot(combine(prev, new))
    Path(a.out).write_text(json.dumps(snap))
    print(f"{len(snap['countries'])} countries, {len(snap['topic_year_counts'])} topics")


if __name__ == "__main__":
    main()
