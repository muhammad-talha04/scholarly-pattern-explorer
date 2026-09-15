"""
STEP 3b: mine the same sliding-window patterns SEPARATELY for every country.

Run after mine_windows.py:
  python mine_countries.py
  python mine_countries.py --db data/canada.duckdb
  python mine_countries.py --min-papers 500 --min-support 0.01

What "a country's papers" means
-------------------------------
A paper belongs to a country when at least one of its authors had an
institution there (table work_countries). A Pakistan-Canada paper therefore
counts for BOTH countries. That is the standard way bibliometric studies count
national output ("whole counting").

Why a separate, higher --min-support than mine_windows.py
---------------------------------------------------------
A country has far fewer papers per window than the whole corpus. At 400 papers,
support 0.005 means "2 papers", which is noise. So the default here is 0.01
AND every pattern must be backed by at least --min-count papers.

Output tables (the app reads them when you pick a country):
  country_patterns  same columns as patterns + country
  country_rules     same columns as rules    + country
"""
from __future__ import annotations

import argparse
import time
from collections import defaultdict

import pandas as pd

from dbconn import DB
from fpgrowth import association_rules, frequent_itemsets

SEP = " | "


def ensure_work_countries(db: DB) -> None:
    """Older databases (e.g. canada.duckdb) were built before work_countries
    existed. Derive it from each author's institution country so they still
    work. build_db.py builds a more complete version from the raw JSON."""
    try:
        db.df("SELECT 1 FROM work_countries LIMIT 1")
        return
    except Exception:                                          # noqa: BLE001
        pass
    print("work_countries missing - deriving it from authors.country")
    db.exec("""
        CREATE TABLE work_countries AS
        SELECT DISTINCT wa.work_id, UPPER(a.country) AS country
        FROM work_authors wa
        JOIN authors a ON a.author_id = wa.author_id
        WHERE a.country IS NOT NULL AND a.country <> ''
    """)
    db.exec("CREATE INDEX IF NOT EXISTS idx_wc_country ON work_countries (country)")
    db.commit()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/openalex.duckdb")
    ap.add_argument("--window", type=int, default=3)
    ap.add_argument("--step", type=int, default=1)
    ap.add_argument("--min-papers", type=int, default=300,
                    help="skip countries with fewer papers than this in total")
    ap.add_argument("--min-window-papers", type=int, default=50,
                    help="skip a country's window if it has fewer papers")
    ap.add_argument("--min-support", type=float, default=0.01)
    ap.add_argument("--min-count", type=int, default=5,
                    help="a pattern must appear in at least this many papers")
    ap.add_argument("--min-confidence", type=float, default=0.5)
    ap.add_argument("--max-len", type=int, default=3)
    args = ap.parse_args()

    t_start = time.perf_counter()
    db = DB(args.db)
    print(f"engine {db.kind} -> {db.path}")
    ensure_work_countries(db)

    db.exec("DROP TABLE IF EXISTS country_patterns")
    db.exec("DROP TABLE IF EXISTS country_rules")
    db.exec("""CREATE TABLE country_patterns (
        country VARCHAR, window_start INTEGER, window_end INTEGER, itemset VARCHAR,
        k INTEGER, support_count INTEGER, n_tx INTEGER, support DOUBLE)""")
    db.exec("""CREATE TABLE country_rules (
        country VARCHAR, window_start INTEGER, antecedent VARCHAR, consequent VARCHAR,
        support DOUBLE, confidence DOUBLE, lift DOUBLE)""")

    counts = db.df("""
        SELECT country, COUNT(*) AS papers FROM work_countries
        GROUP BY country HAVING COUNT(*) >= ? ORDER BY papers DESC
    """, [args.min_papers])
    if counts.empty:
        print("no country has enough papers; lower --min-papers")
        return
    print(f"{len(counts)} countries with >= {args.min_papers:,} papers")

    yrs = db.df("SELECT MIN(pub_year) AS lo, MAX(pub_year) AS hi FROM works")
    lo, hi = int(yrs.lo[0]), int(yrs.hi[0])

    # ONE query for everything, then group in memory. Running 25 window queries
    # per country would be ~1,500 round trips.
    rows = db.df("""
        SELECT wc.country, w.work_id, w.pub_year, t.display_name AS topic
        FROM work_countries wc
        JOIN works w        ON w.work_id  = wc.work_id
        JOIN work_topics wt ON wt.work_id = wc.work_id
        JOIN topics t       ON t.topic_id = wt.topic_id
        WHERE wc.country IN (SELECT country FROM work_countries
                             GROUP BY country HAVING COUNT(*) >= ?)
    """, [args.min_papers])
    print(f"loaded {len(rows):,} (country, paper, topic) rows")

    # country -> year -> {work_id: [topics]}
    by_country: dict[str, dict[int, dict[str, list[str]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list)))
    for c, wid, year, topic in rows.itertuples(index=False, name=None):
        by_country[c][int(year)][wid].append(topic)
    del rows

    all_patterns, all_rules = [], []
    for c in counts.country:
        years = by_country.get(c, {})
        n_pat = 0
        for y0 in range(lo, hi - args.window + 2, args.step):
            y1 = y0 + args.window - 1
            baskets = [tops for y in range(y0, y1 + 1)
                       for tops in years.get(y, {}).values() if len(tops) >= 2]
            if len(baskets) < args.min_window_papers:
                continue
            min_count = max(args.min_count, int(args.min_support * len(baskets) + 0.999))
            itemsets, n_tx = frequent_itemsets(baskets, min_count=min_count,
                                               max_len=args.max_len)
            for s, cnt in itemsets.items():
                all_patterns.append((c, y0, y1, SEP.join(sorted(s)), len(s), cnt,
                                     n_tx, cnt / n_tx))
            n_pat += len(itemsets)
            for r in association_rules(itemsets, n_tx, args.min_confidence):
                all_rules.append((c, y0, r["antecedent"], r["consequent"],
                                  r["support"], r["confidence"], r["lift"]))
        print(f"  {c}: {int(counts.loc[counts.country == c, 'papers'].iloc[0]):>7,} papers "
              f"{n_pat:>7,} pattern rows")

    db.many("INSERT INTO country_patterns VALUES (?,?,?,?,?,?,?,?)", all_patterns)
    db.many("INSERT INTO country_rules VALUES (?,?,?,?,?,?,?)", all_rules)
    db.exec("CREATE INDEX IF NOT EXISTS idx_cp ON country_patterns (country, window_start)")
    db.exec("CREATE INDEX IF NOT EXISTS idx_cr ON country_rules (country, window_start)")
    db.commit()
    db.close()
    print(f"\nstored {len(all_patterns):,} country pattern rows and "
          f"{len(all_rules):,} rules in {time.perf_counter() - t_start:.0f}s")
    print("done. next:  streamlit run app.py  (pick a country in the sidebar)")


if __name__ == "__main__":
    main()
