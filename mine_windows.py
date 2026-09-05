"""
STEP 3: the research part. Mine frequent topic combinations in SLIDING WINDOWS
of years, so you see patterns being born and dying instead of one flat list.

Run examples
------------
  python mine_windows.py
  python mine_windows.py --window 3 --step 1 --min-support 0.02 --max-len 3
  python mine_windows.py --field "Computer Science" --exclude-topic "Deep Learning"
  python mine_windows.py --min-score 0.6            # only confident topic tags

Two ideas make this a research contribution rather than a tutorial:

1. SLIDING WINDOWS. Each window is its own transaction database. A pattern's
   support becomes a time series, so "Transformers + NLP" can be shown arriving
   in 2019 and "Fuzzy Logic + Expert Systems" fading after 2012.

2. CONSTRAINT PUSH-DOWN. The user's filters (field, topic must/must-not appear,
   minimum tag confidence) are put inside the SQL WHERE clause, so the database
   throws rows away BEFORE the miner ever sees them. That is much faster than
   mining everything and filtering afterwards, and it is the standard
   "constrained frequent pattern mining" formulation.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from dbconn import DB
from fpgrowth import association_rules, frequent_itemsets

SEP = " | "


def build_where(args):
    """Turn command-line filters into a SQL WHERE fragment + parameter list."""
    where = ["w.pub_year BETWEEN ? AND ?", "wt.score >= ?"]
    params_tail = [args.min_score]

    if args.field:
        where.append("t.field = ?")
        params_tail.append(args.field)
    if args.exclude_topic:
        marks = ",".join("?" for _ in args.exclude_topic)
        where.append(f"t.display_name NOT IN ({marks})")
        params_tail.extend(args.exclude_topic)

    return " AND ".join(where), params_tail


def baskets_for_window(db, y0, y1, where_sql, params_tail, include_topic):
    """
    One SQL query -> one list of baskets.
    A basket is one paper; the items in it are that paper's topic names.
    """
    sql = f"""
        SELECT wt.work_id, t.display_name
        FROM work_topics wt
        JOIN topics t ON t.topic_id = wt.topic_id
        JOIN works  w ON w.work_id  = wt.work_id
        WHERE {where_sql}
        ORDER BY wt.work_id
    """
    rows = db.df(sql, [y0, y1] + list(params_tail))

    grouped = {}
    for work_id, topic in rows.itertuples(index=False):
        grouped.setdefault(work_id, []).append(topic)

    baskets = [v for v in grouped.values() if len(v) >= 2]
    if include_topic:                      # keep only baskets containing this topic
        baskets = [b for b in baskets if include_topic in b]
    return baskets

def emerging_report(db, top=8):
    """
    Which topic combinations grew the most, and which collapsed?

    We compare each pattern's support in its EARLIEST window against its
    LATEST window, using SQL window functions (FIRST_VALUE / LAST_VALUE).
    """
    sql = """
        WITH ranked AS (
            SELECT itemset, k, window_start, support,
                   ROW_NUMBER() OVER (PARTITION BY itemset ORDER BY window_start)      AS rn_first,
                   ROW_NUMBER() OVER (PARTITION BY itemset ORDER BY window_start DESC) AS rn_last
            FROM patterns
            WHERE k >= 2
        ),
        firsts AS (SELECT itemset, support AS first_support, window_start AS first_win
                   FROM ranked WHERE rn_first = 1),
        lasts  AS (SELECT itemset, support AS last_support,  window_start AS last_win
                   FROM ranked WHERE rn_last  = 1)
        SELECT f.itemset,
               f.first_win, ROUND(f.first_support, 4) AS first_support,
               l.last_win,  ROUND(l.last_support, 4)  AS last_support,
               ROUND(l.last_support - f.first_support, 4) AS change
        FROM firsts f JOIN lasts l ON l.itemset = f.itemset
        ORDER BY change DESC
    """
    df = db.df(sql)
    if df.empty:
        print("no multi-item patterns found - lower --min-support and try again")
        return
    print("\nEMERGING patterns (support grew the most):")
    print(df.head(top).to_string(index=False))
    print("\nDECLINING patterns (support fell the most):")
    print(df.tail(top).iloc[::-1].to_string(index=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/openalex.duckdb")
    ap.add_argument("--window", type=int, default=3, help="window length in years")
    ap.add_argument("--step", type=int, default=1, help="years to slide each time")
    ap.add_argument("--min-support", type=float, default=0.02)
    ap.add_argument("--min-confidence", type=float, default=0.5)
    ap.add_argument("--max-len", type=int, default=3)
    ap.add_argument("--min-score", type=float, default=0.0, help="min topic-tag score")
    ap.add_argument("--field", default=None, help='e.g. "Computer Science"')
    ap.add_argument("--include-topic", default=None, help="basket must contain this")
    ap.add_argument("--exclude-topic", action="append", default=[])
    args = ap.parse_args()

    db = DB(args.db)
    print(f"engine {db.kind} -> {db.path}")
    db.exec("DELETE FROM patterns")
    db.exec("DELETE FROM rules")

    yrs = db.df("SELECT MIN(pub_year) AS lo, MAX(pub_year) AS hi FROM works")
    lo, hi = int(yrs.lo[0]), int(yrs.hi[0])
    where_sql, params_tail = build_where(args)

    total_patterns = 0
    for y0 in range(lo, hi - args.window + 2, args.step):
        y1 = y0 + args.window - 1
        baskets = baskets_for_window(db, y0, y1, where_sql, params_tail, args.include_topic)
        if len(baskets) < 20:
            continue

        itemsets, n_tx = frequent_itemsets(
            baskets, min_support=args.min_support, max_len=args.max_len
        )
        rows = [
            (y0, y1, SEP.join(sorted(s)), len(s), c, n_tx, c / n_tx)
            for s, c in itemsets.items()
        ]
        db.many("INSERT INTO patterns VALUES (?,?,?,?,?,?,?)", rows)

        rules = association_rules(itemsets, n_tx, args.min_confidence)
        db.many(
            "INSERT INTO rules VALUES (?,?,?,?,?,?)",
            [(y0, r["antecedent"], r["consequent"], r["support"],
              r["confidence"], r["lift"]) for r in rules],
        )
        total_patterns += len(rows)
        print(f"  {y0}-{y1}: {n_tx:>6,} papers  {len(rows):>5} itemsets  {len(rules):>5} rules")

    db.commit()
    print(f"\nstored {total_patterns:,} pattern rows in the database")
    emerging_report(db)
    db.close()
    print("\ndone. next:  streamlit run app.py")


if __name__ == "__main__":
    main()

