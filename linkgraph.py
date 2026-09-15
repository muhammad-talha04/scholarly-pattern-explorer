"""Co-authorship graph construction + temporal train/test split for link prediction.

Reads the same DuckDB database the pattern miner builds (works, authors,
work_authors, work_topics, topics). Column and table names are discovered at
runtime, so small naming differences in schema.sql do not break anything.

The split is TEMPORAL, which is the part that makes the experiment honest:
  train graph  = every co-authorship in years <= split_year
  test positives = author pairs whose FIRST collaboration falls in
                   (split_year, split_year + horizon]
  test negatives = same number of random pairs that never collaborate at all
Both authors of every test pair must already exist in the train graph with at
least `min_degree` collaborations, otherwise the task degenerates into
predicting authors the model has never seen.

Run `python linkgraph.py --db data/canada.duckdb --check` first: it prints the
schema it resolved and the split sizes, and fails loudly if anything is off.
"""

import argparse
import random
import sys
from collections import defaultdict
from dataclasses import dataclass, field

import duckdb


# ---------------------------------------------------------------- schema ----

def _tables(con):
    return [r[0] for r in con.execute("SHOW TABLES").fetchall()]


def _cols(con, table):
    return [r[1] for r in con.execute(f"PRAGMA table_info('{table}')").fetchall()]


def _pick(names, *needles, forbid=()):
    """First name containing every needle (case-insensitive) and no forbidden word."""
    for n in names:
        low = n.lower()
        if all(k in low for k in needles) and not any(f in low for f in forbid):
            return n
    return None


@dataclass
class Schema:
    works: str; works_id: str; works_year: str
    authors: str; authors_id: str; authors_name: str
    wa: str; wa_work: str; wa_author: str
    wt: str; wt_work: str; wt_topic: str
    topics: str; topics_id: str; topics_name: str


def resolve_schema(con):
    tabs = _tables(con)

    def need_table(*needles, forbid=()):
        t = _pick(tabs, *needles, forbid=forbid)
        if t is None:
            raise SystemExit(f"Could not find a table matching {needles} "
                             f"among tables: {tabs}")
        return t

    works = need_table("work", forbid=("author", "topic", "country"))
    authors = need_table("author", forbid=("work",))
    topics = need_table("topic", forbid=("work",))
    wa = need_table("work", "author")
    wt = need_table("work", "topic")

    def need_col(table, *needles, forbid=()):
        c = _pick(_cols(con, table), *needles, forbid=forbid)
        if c is None:
            raise SystemExit(f"Could not find a column matching {needles} in "
                             f"table {table}; its columns are: {_cols(con, table)}")
        return c

    return Schema(
        works=works,
        works_id=need_col(works, "id", forbid=("topic", "author", "source")),
        works_year=need_col(works, "year"),
        authors=authors,
        authors_id=need_col(authors, "id", forbid=("work",)),
        authors_name=need_col(authors, "name"),
        wa=wa,
        wa_work=need_col(wa, "work"),
        wa_author=need_col(wa, "author"),
        wt=wt,
        wt_work=need_col(wt, "work"),
        wt_topic=need_col(wt, "topic"),
        topics=topics,
        topics_id=need_col(topics, "id", forbid=("work",)),
        topics_name=need_col(topics, "name"),
    )


# ------------------------------------------------------------- raw pairs ----

def load_coauthor_pairs(con, S, max_authors_per_work=25):
    """Return {(a, b): first_year} for every co-author pair, a < b.

    Works with more than `max_authors_per_work` authors are skipped:
    hyper-authored papers (large consortia) add quadratically many weak links
    and are standard to exclude in co-authorship studies.
    """
    rows = con.execute(
        f"SELECT wa.{S.wa_work}, wa.{S.wa_author}, w.{S.works_year} "
        f"FROM {S.wa} wa JOIN {S.works} w ON wa.{S.wa_work} = w.{S.works_id} "
        f"WHERE w.{S.works_year} IS NOT NULL"
    ).fetchall()

    by_work = defaultdict(list)
    year_of = {}
    for work, author, year in rows:
        by_work[work].append(author)
        year_of[work] = int(year)

    first_year = {}
    skipped = 0
    for work, auths in by_work.items():
        auths = sorted(set(auths))
        if len(auths) < 2:
            continue
        if len(auths) > max_authors_per_work:
            skipped += 1
            continue
        y = year_of[work]
        for i in range(len(auths)):
            for j in range(i + 1, len(auths)):
                pair = (auths[i], auths[j])
                if pair not in first_year or y < first_year[pair]:
                    first_year[pair] = y
    if skipped:
        print(f"  (skipped {skipped} hyper-authored works "
              f"with > {max_authors_per_work} authors)")
    return first_year


def load_author_topics(con, S, max_year):
    """{author_id: set(topic_id)} using only works up to max_year (no leakage)."""
    rows = con.execute(
        f"SELECT wa.{S.wa_author}, wt.{S.wt_topic} "
        f"FROM {S.wa} wa "
        f"JOIN {S.wt} wt ON wa.{S.wa_work} = wt.{S.wt_work} "
        f"JOIN {S.works} w ON wa.{S.wa_work} = w.{S.works_id} "
        f"WHERE w.{S.works_year} <= ?", [max_year]
    ).fetchall()
    out = defaultdict(set)
    for author, topic in rows:
        out[author].add(topic)
    return out


def load_author_names(con, S, ids):
    ids = list(ids)
    if not ids:
        return {}
    con.execute("CREATE OR REPLACE TEMP TABLE _want(id VARCHAR)")
    con.executemany("INSERT INTO _want VALUES (?)", [(str(i),) for i in ids])
    rows = con.execute(
        f"SELECT a.{S.authors_id}, a.{S.authors_name} FROM {S.authors} a "
        f"JOIN _want ON CAST(a.{S.authors_id} AS VARCHAR) = _want.id"
    ).fetchall()
    return {r[0]: r[1] for r in rows}


# ----------------------------------------------------------------- split ----

@dataclass
class LinkSplit:
    train_edges: set                    # {(a,b)} a < b, years <= split_year
    adj: dict                           # {node: set(neighbors)} train graph
    test_pos: list                      # [(a,b)] new pairs in the horizon
    test_neg: list                      # [(a,b)] sampled non-edges
    nodes: list = field(default_factory=list)   # eligible nodes, sorted
    index: dict = field(default_factory=dict)   # node -> int
    split_year: int = 0

    @property
    def num_nodes(self):
        return len(self.nodes)


def temporal_split(first_year, split_year, horizon=3, min_degree=2, seed=0):
    train_edges = {p for p, y in first_year.items() if y <= split_year}
    if not train_edges:
        raise SystemExit(f"No training edges at split_year={split_year}. "
                         "Pick a later year (check --check output for the year range).")

    adj = defaultdict(set)
    for a, b in train_edges:
        adj[a].add(b)
        adj[b].add(a)

    eligible = {n for n, nbrs in adj.items() if len(nbrs) >= min_degree}

    test_pos = sorted(
        p for p, y in first_year.items()
        if split_year < y <= split_year + horizon
        and p not in train_edges
        and p[0] in eligible and p[1] in eligible
    )
    if len(test_pos) < 50:
        print(f"WARNING: only {len(test_pos)} test positives — metrics will be "
              "noisy. Try an earlier --split-year or --min-degree 1.")

    nodes = sorted(eligible)
    rng = random.Random(seed)
    known = set(first_year)  # never sample ANY real pair (any year) as negative
    test_neg, seen = [], set()
    while len(test_neg) < len(test_pos):
        a, b = rng.choice(nodes), rng.choice(nodes)
        if a == b:
            continue
        p = (a, b) if a < b else (b, a)
        if p in known or p in seen:
            continue
        seen.add(p)
        test_neg.append(p)

    return LinkSplit(
        train_edges=train_edges,
        adj={n: adj[n] for n in nodes},
        test_pos=test_pos,
        test_neg=test_neg,
        nodes=nodes,
        index={n: i for i, n in enumerate(nodes)},
        split_year=split_year,
    )


# ----------------------------------------------------------------- check ----

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default="data/canada.duckdb")
    ap.add_argument("--split-year", type=int, default=2021)
    ap.add_argument("--horizon", type=int, default=3)
    ap.add_argument("--min-degree", type=int, default=2)
    ap.add_argument("--check", action="store_true",
                    help="resolve schema, build the split, print a report")
    args = ap.parse_args()

    con = duckdb.connect(args.db, read_only=True)
    S = resolve_schema(con)
    print("Schema resolved:")
    for k, v in vars(S).items():
        print(f"  {k:12} = {v}")

    print("\nLoading co-author pairs ...")
    fy = load_coauthor_pairs(con, S)
    years = sorted(set(fy.values()))
    print(f"  {len(fy):,} distinct author pairs, years {years[0]}–{years[-1]}")

    sp = temporal_split(fy, args.split_year, args.horizon, args.min_degree)
    print(f"\nTemporal split at {args.split_year} "
          f"(predicting {args.split_year + 1}–{args.split_year + args.horizon}):")
    print(f"  train edges     : {len(sp.train_edges):,}")
    print(f"  eligible authors: {sp.num_nodes:,} (train degree >= {args.min_degree})")
    print(f"  test positives  : {len(sp.test_pos):,} (brand-new collaborations)")
    print(f"  test negatives  : {len(sp.test_neg):,} (sampled non-pairs)")
    print("\nOK — linkgraph self-check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
