"""
STEP 2: turn the downloaded JSON into a real relational database.

Input : one JSON object per line (from make_sample_data.py or fetch_openalex.py)
Output: data/openalex.duckdb  (or .sqlite if DuckDB is not installed)

Run:  python build_db.py --input data/works_sample.jsonl

What it does, in database language: it takes one big nested document and
normalizes it into 5 tables plus 2 bridge tables, so that every fact is stored
exactly once, and every question the app asks can be answered with a join
rather than by re-parsing JSON.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from dbconn import DB


def short_id(url: str | None) -> str | None:
    """'https://openalex.org/W123' -> 'W123'. Shorter keys, same meaning."""
    return url.rsplit("/", 1)[-1] if url else None


def load(input_path: str, db_path: str):
    works, topics, authors = {}, {}, {}
    work_topics, work_authors = {}, {}
    skipped = 0
    t0 = time.perf_counter()

    with open(input_path, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            if n % 25_000 == 0:
                print(f"  parsed {n:>9,} lines  ({time.perf_counter() - t0:5.1f}s)")
            line = line.strip()
            if not line:
                continue
            try:
                w = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue

            wid = short_id(w.get("id"))
            year = w.get("publication_year")
            # No id or no year = useless to us: every window query needs the year.
            if not wid or year is None:
                skipped += 1
                continue

            auths = w.get("authorships") or []
            works[wid] = (
                wid,
                (w.get("display_name") or w.get("title") or "")[:300],
                year,
                w.get("cited_by_count") or 0,
                len(auths),
            )

            for t in w.get("topics") or []:
                tid = short_id(t.get("id"))
                if not tid:
                    continue
                topics[tid] = (
                    tid,
                    t.get("display_name"),
                    (t.get("field") or {}).get("display_name"),
                    (t.get("domain") or {}).get("display_name"),
                )
                work_topics[(wid, tid)] = (wid, tid, t.get("score") or 0.0)

            for pos, a in enumerate(auths):
                info = a.get("author") or {}
                aid = short_id(info.get("id"))
                if not aid:
                    continue
                inst = (a.get("institutions") or [{}])[0]
                authors[aid] = (
                    aid,
                    info.get("display_name"),
                    inst.get("display_name"),
                    inst.get("country_code"),
                )
                work_authors[(wid, aid)] = (wid, aid, pos)

    return works, topics, authors, work_topics, work_authors, skipped

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="data/works_sample.jsonl")
    ap.add_argument("--db", default="data/openalex.duckdb")
    args = ap.parse_args()

    Path("data").mkdir(exist_ok=True)
    print(f"reading {args.input} ...")
    works, topics, authors, work_topics, work_authors, skipped = load(args.input, args.db)

    print(f"  works        {len(works):>9,}")
    print(f"  topics       {len(topics):>9,}")
    print(f"  authors      {len(authors):>9,}")
    print(f"  work_topics  {len(work_topics):>9,}")
    print(f"  work_authors {len(work_authors):>9,}")
    if skipped:
        print(f"  skipped bad or year-less lines: {skipped:,}")

    db = DB(args.db)
    print(f"\ndatabase engine: {db.kind}  ->  {db.path}")
    db.script(Path("schema.sql").read_text(encoding="utf-8"))

    # Load the tables first, build the indexes afterwards. See indexes.sql.
    for table, cols, rows in [
        ("works",        5, works),
        ("topics",       4, topics),
        ("authors",      4, authors),
        ("work_topics",  3, work_topics),
        ("work_authors", 3, work_authors),
    ]:
        marks = ",".join("?" * cols)
        t0 = time.perf_counter()
        db.many(f"INSERT INTO {table} VALUES ({marks})", rows.values())
        print(f"  loaded {table:<13} {len(rows):>9,} rows  "
              f"{time.perf_counter() - t0:6.1f}s")

    t0 = time.perf_counter()
    db.script(Path("indexes.sql").read_text(encoding="utf-8"))
    db.commit()
    print(f"  built indexes                       {time.perf_counter() - t0:6.1f}s")

    # --- sanity checks you should always run after loading data ---
    print("\nsanity check 1 - papers per year (first 5 rows):")
    print(db.df("""
        SELECT pub_year, COUNT(*) AS papers
        FROM works GROUP BY pub_year ORDER BY pub_year
    """).head().to_string(index=False))

    print("\nsanity check 2 - top 5 topics overall:")
    print(db.df("""
        SELECT t.display_name, COUNT(*) AS papers
        FROM work_topics wt JOIN topics t ON t.topic_id = wt.topic_id
        GROUP BY t.display_name
        ORDER BY papers DESC
        LIMIT 5
    """).to_string(index=False))

    print("\nsanity check 3 - orphan rows (must both be 0):")
    orphans = db.df("""
        SELECT
          (SELECT COUNT(*) FROM work_topics wt
             LEFT JOIN works w ON w.work_id = wt.work_id WHERE w.work_id IS NULL) AS topic_orphans,
          (SELECT COUNT(*) FROM work_authors wa
             LEFT JOIN works w ON w.work_id = wa.work_id WHERE w.work_id IS NULL) AS author_orphans
    """)
    print(orphans.to_string(index=False))

    db.close()
    print("\ndone. next:  python mine_windows.py")


if __name__ == "__main__":
    main()

