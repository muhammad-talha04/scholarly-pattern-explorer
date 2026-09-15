"""Answer ONE question: what is actually inside data/works_real.jsonl?

READ-ONLY. It never changes any file. Safe to run any time.

Run:  python check_corpus.py
      python check_corpus.py --tail 14861     # compare the last 14,861 lines

Why this matters
----------------
Pattern "support" means "share of papers in a window that contain this topic
pair". That number only means something if every paper in the file was chosen
by the SAME rule. If the first 188k papers are "AI, cited 20+" and the next
15k are "all of CS, cited 0+", the 2024-2026 windows suddenly fill with a
different kind of paper and your emerging/declining results shift for reasons
that have nothing to do with research trends.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def subfield_of(work: dict) -> str:
    topics = work.get("topics") or []
    if not topics:
        return "none"
    sf = (topics[0].get("subfield") or {})
    sid = (sf.get("id") or "").rsplit("/", 1)[-1]
    return f"{sid} {sf.get('display_name') or ''}".strip() or "unknown"


def summarize(label: str, rows: list[dict]) -> None:
    n = len(rows)
    if not n:
        print(f"\n[{label}] no rows")
        return
    cited = [r.get("cited_by_count") or 0 for r in rows]
    years = Counter(r.get("publication_year") for r in rows)
    subs = Counter(subfield_of(r) for r in rows)
    print(f"\n[{label}]  {n:,} rows")
    print(f"  cited_by_count >= 20 : {sum(c >= 20 for c in cited) / n:6.1%}")
    print(f"  cited_by_count >= 10 : {sum(c >= 10 for c in cited) / n:6.1%}")
    print(f"  cited_by_count == 0  : {sum(c == 0 for c in cited) / n:6.1%}")
    print(f"  min cited            : {min(cited)}")
    print("  top subfields (of the first topic):")
    for name, k in subs.most_common(5):
        print(f"     {k / n:6.1%}  {name}")
    print("  newest years:", ", ".join(f"{y}: {years[y]:,}"
                                      for y in sorted(years, key=lambda y: y or 0)[-4:]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="data/works_real.jsonl")
    ap.add_argument("--state", default="data/fetch_state.json")
    ap.add_argument("--tail", type=int, default=None,
                    help="how many lines at the END to treat as 'recently added' "
                         "(default: refresh_appended from fetch_state.json)")
    args = ap.parse_args()

    tail = args.tail
    if tail is None and Path(args.state).exists():
        tail = json.loads(Path(args.state).read_text(encoding="utf-8")).get("refresh_appended") or 0
    tail = tail or 0

    rows, bad, ids = [], 0, Counter()
    with open(args.input, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                w = json.loads(line)
            except ValueError:
                bad += 1
                continue
            ids[w.get("id")] += 1
            # keep only the small fields, so 1 GB of JSON fits in memory
            rows.append({
                "id": w.get("id"),
                "publication_year": w.get("publication_year"),
                "cited_by_count": w.get("cited_by_count"),
                "topics": (w.get("topics") or [])[:1],
            })

    total = len(rows)
    dupes = sum(k - 1 for k in ids.values() if k > 1)
    print(f"file              : {args.input}")
    print(f"lines (valid)     : {total:,}")
    print(f"broken lines      : {bad:,}")
    print(f"unique ids        : {len(ids):,}")
    print(f"duplicate lines   : {dupes:,}")

    split = max(0, total - tail)
    summarize(f"ORIGINAL part: lines 1 .. {split:,}", rows[:split])
    if tail:
        summarize(f"RECENTLY ADDED part: last {tail:,} lines", rows[split:])

    print("\nHow to read this:")
    print("  If the two parts look different (e.g. original is ~100% cited>=20 in")
    print("  one subfield, recent part is mostly cited==0 across many subfields),")
    print("  the recent lines were downloaded with a different rule.")
    print(f"  Fix:  python clean_corpus.py --keep-first {split} --subfield-id <id> --min-cited <n>")


if __name__ == "__main__":
    main()
