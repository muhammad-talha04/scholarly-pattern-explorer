"""Per-country analytics, produced as schemas.CountryStats-shaped dicts.

Incremental: counts from the previous snapshot are combined with the new
works only, so a run never re-reads the whole corpus.
"""
from __future__ import annotations
import argparse, json, sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from countries import COUNTRIES  # noqa: E402  (existing ISO table in repo root)


def tally(works) -> dict:
    """Raw counters: papers per country per year, topics per country, co-authorship pairs."""
    by_year, topics, pairs = defaultdict(Counter), defaultdict(Counter), Counter()
    for w in works:
        cs = w.get("countries") or []
        for c in cs:
            by_year[c][str(w.get("year"))] += 1
            topics[c].update(w.get("topics", [])[:3])
        for i, a in enumerate(cs):
            for b in cs[i + 1:]:
                pairs[f"{a}-{b}"] += 1
    return {"by_year": by_year, "topics": topics, "pairs": pairs}


def combine(prev: dict | None, new: dict) -> dict:
    if not prev:
        return new
    out = {}
    for key in ("by_year", "topics"):
        merged = defaultdict(Counter, {k: Counter(v) for k, v in prev[key].items()})
        for c, cnt in new[key].items():
            merged[c].update(cnt)
        out[key] = merged
    out["pairs"] = Counter(prev["pairs"]) + new["pairs"]
    return out


def to_stats(t: dict, top_n: int = 5) -> list[dict]:
    rows = []
    for code, years in t["by_year"].items():
        ys = sorted((int(y), n) for y, n in years.items() if y.isdigit())
        growth = None
        if len(ys) >= 2 and ys[-2][1]:
            growth = round(100 * (ys[-1][1] - ys[-2][1]) / ys[-2][1], 1)
        rows.append({"code": code, "name": COUNTRIES.get(code, (code,))[0],
                     "papers": sum(years.values()), "growth_pct": growth,
                     "top_topics": [n for n, _ in t["topics"][code].most_common(top_n)]})
    return sorted(rows, key=lambda r: -r["papers"])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--new", required=True, help="JSONL of works added this run")
    ap.add_argument("--prev", help="previous tally JSON")
    ap.add_argument("--out", default="data/country_snapshot.json")
    a = ap.parse_args(argv)
    with open(a.new, encoding="utf-8") as fh:
        new = tally(json.loads(l) for l in fh if l.strip())
    prev = json.loads(Path(a.prev).read_text())["tally"] if a.prev and Path(a.prev).exists() else None
    t = combine(prev, new)
    Path(a.out).write_text(json.dumps({"tally": t, "countries": to_stats(t),
                                       "top_collaborations": t["pairs"].most_common(50)}))
    print(f"{len(t['by_year'])} countries")


if __name__ == "__main__":
    main()
