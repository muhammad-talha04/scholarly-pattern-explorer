"""Make a CLEAN copy of works_real.jsonl where every paper follows one rule.

It NEVER overwrites your file. It writes a new file next to it, prints what it
kept and dropped, and you decide whether to swap them.

Run (example for "AI subfield, cited 20+"):
  python clean_corpus.py --keep-first 188462 --subfield-id 1702 --min-cited 20

  --keep-first N   the first N lines are your original download: kept as-is
  every later line is kept only if it passes --subfield-id and --min-cited
  duplicates (same id) are removed everywhere; the LAST copy wins, because it
  has the newest citation count

Output: data/works_real.cleaned.jsonl
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def first_subfield_id(work: dict) -> str:
    topics = work.get("topics") or []
    if not topics:
        return ""
    return ((topics[0].get("subfield") or {}).get("id") or "").rsplit("/", 1)[-1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="data/works_real.jsonl")
    ap.add_argument("--output", default="data/works_real.cleaned.jsonl")
    ap.add_argument("--keep-first", type=int, required=True)
    ap.add_argument("--subfield-id", default=None)
    ap.add_argument("--min-cited", type=int, default=0)
    args = ap.parse_args()

    src, dst = Path(args.input), Path(args.output)
    if dst.exists():
        raise SystemExit(f"{dst} already exists. Delete or rename it first.")

    def passes(w: dict, n: int) -> bool:
        if n <= args.keep_first:
            return True
        if args.subfield_id and first_subfield_id(w) != str(args.subfield_id):
            return False
        return (w.get("cited_by_count") or 0) >= args.min_cited

    # pass 1: for each id, the line number of its LAST copy that passes the rule
    last_line: dict[str, int] = {}
    with src.open(encoding="utf-8") as fh:
        n = 0
        for line in fh:
            try:
                w = json.loads(line)
            except ValueError:
                continue
            n += 1          # counts valid lines only, same as check_corpus.py
            if w.get("id") and passes(w, n):
                last_line[w["id"]] = n

    kept = dropped_rule = dropped_dupe = broken = 0
    with src.open(encoding="utf-8") as fh, dst.open("w", encoding="utf-8") as out:
        n = 0
        for line in fh:
            try:
                w = json.loads(line)
            except ValueError:
                if line.strip():
                    broken += 1
                continue
            n += 1
            wid = w.get("id")
            if not passes(w, n):
                dropped_rule += 1
                continue
            if not wid or last_line.get(wid) != n:
                dropped_dupe += 1
                continue
            out.write(line if line.endswith("\n") else line + "\n")
            kept += 1

    print(f"kept                    {kept:,}")
    print(f"dropped (wrong slice)   {dropped_rule:,}")
    print(f"dropped (duplicate id)  {dropped_dupe:,}")
    print(f"dropped (broken JSON)   {broken:,}")
    print(f"\nwrote {dst}")
    print("Check the numbers. If they look right, swap the files (see guide, Part 3).")


if __name__ == "__main__":
    main()
