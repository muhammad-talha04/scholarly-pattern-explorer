"""
STEP 4a: every database question the web app needs, in one tested place.

The app (app.py) contains NO SQL. It only calls functions from here. That split
matters: this file can be tested from the command line, a Streamlit app cannot.

Self-test:  python analytics.py --db data/openalex.duckdb
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from dbconn import DB


def year_range(db):
    r = db.df("SELECT MIN(pub_year) AS lo, MAX(pub_year) AS hi FROM works")
    return int(r.lo[0]), int(r.hi[0])


def windows(db) -> pd.DataFrame:
    return db.df("""
        SELECT window_start, window_end, MAX(n_tx) AS papers, COUNT(*) AS itemsets
        FROM patterns GROUP BY window_start, window_end ORDER BY window_start
    """)


def corpus_summary(db) -> pd.DataFrame:
    """
    One row of headline counts for the summary strip at the top of the app.

    Five scalar sub-queries in a single statement, so the whole strip costs one
    round trip to the database instead of five.
    """
    return db.df("""
        SELECT (SELECT COUNT(*) FROM works)    AS works,
               (SELECT COUNT(*) FROM topics)   AS topics,
               (SELECT COUNT(*) FROM authors)  AS authors,
               (SELECT COUNT(*) FROM patterns) AS patterns,
               (SELECT COUNT(*) FROM rules)    AS rules
    """)


def topic_distribution(db, y0, y1, limit=20) -> pd.DataFrame:
    """VIEW 1 - the raw data: how often does each topic appear in this window?"""
    return db.df("""
        SELECT t.display_name AS topic, t.field, COUNT(*) AS papers
        FROM work_topics wt
        JOIN topics t ON t.topic_id = wt.topic_id
        JOIN works  w ON w.work_id  = wt.work_id
        WHERE w.pub_year BETWEEN ? AND ?
        GROUP BY t.display_name, t.field
        ORDER BY papers DESC
        LIMIT ?
    """, [y0, y1, limit])


def patterns_for_window(db, y0, min_k=2, limit=40) -> pd.DataFrame:
    """VIEW 2 - the mining results for one window."""
    return db.df("""
        SELECT itemset, k, support_count, n_tx, support
        FROM patterns
        WHERE window_start = ? AND k >= ?
        ORDER BY support DESC
        LIMIT ?
    """, [y0, min_k, limit])


def pattern_timeseries(db, itemsets: list[str]) -> pd.DataFrame:
    """
    VIEW 3 - the same patterns tracked across every window.

    A pattern that was not frequent in a window has NO ROW in the patterns
    table. If we plotted only the rows we have, an emerging pattern would look
    like a short line floating in the middle of the chart. So we fill the
    missing windows with support 0: now the line visibly climbs from zero,
    which is the actual claim we are making.
    """
    empty = pd.DataFrame(columns=["itemset", "window_start", "support"])
    if not itemsets:
        return empty
    marks = ",".join("?" for _ in itemsets)
    found = db.df(f"""
        SELECT itemset, window_start, support
        FROM patterns
        WHERE itemset IN ({marks})
        ORDER BY itemset, window_start
    """, list(itemsets))
    if found.empty:
        return empty

    all_windows = db.df("SELECT DISTINCT window_start FROM patterns "
                        "ORDER BY window_start")["window_start"].tolist()
    grid = pd.MultiIndex.from_product(
        [sorted(found["itemset"].unique()), all_windows],
        names=["itemset", "window_start"],
    )
    return (found.set_index(["itemset", "window_start"])
                 .reindex(grid, fill_value=0.0)
                 .reset_index())


def short_label(itemset: str, per_item: int = 20) -> str:
    """
    Squeeze 'A very long topic name | Another long one' into something a chart
    legend can actually show, without losing which pattern it is.
    """
    parts = [p if len(p) <= per_item else p[:per_item - 1] + "…"
             for p in itemset.split(" | ")]
    return " + ".join(parts)


def cooccurrence_matrix(db, y0, y1, top_n=12) -> pd.DataFrame:
    """A topic-by-topic count table, built with a SELF JOIN on the bridge table."""
    top = topic_distribution(db, y0, y1, top_n)["topic"].tolist()
    if len(top) < 2:
        return pd.DataFrame()
    marks = ",".join("?" for _ in top)
    pairs = db.df(f"""
        SELECT a.display_name AS topic_a, b.display_name AS topic_b, COUNT(*) AS papers
        FROM work_topics wa
        JOIN work_topics wb ON wb.work_id = wa.work_id AND wb.topic_id <> wa.topic_id
        JOIN topics a ON a.topic_id = wa.topic_id
        JOIN topics b ON b.topic_id = wb.topic_id
        JOIN works  w ON w.work_id  = wa.work_id
        WHERE w.pub_year BETWEEN ? AND ?
          AND a.display_name IN ({marks}) AND b.display_name IN ({marks})
        GROUP BY a.display_name, b.display_name
    """, [y0, y1] + top + top)
    if pairs.empty:
        return pd.DataFrame()
    return pairs.pivot(index="topic_a", columns="topic_b", values="papers").fillna(0)


def top_rules(db, y0, min_lift=1.1, limit=25) -> pd.DataFrame:
    return db.df("""
        SELECT antecedent, consequent, support, confidence, lift
        FROM rules
        WHERE window_start = ? AND lift >= ?
        ORDER BY lift DESC
        LIMIT ?
    """, [y0, min_lift, limit])

def coauthor_edges(db, y0, y1, min_papers=2, limit=600, itemset=None) -> pd.DataFrame:
    """
    VIEW 4 - the social network. Two authors are linked if they co-wrote papers.

    Built with a SELF JOIN on work_authors, keeping a<b so each pair appears once.

    If `itemset` is given ('Topic A | Topic B'), we first select only the papers
    that contain EVERY topic in that pattern, then build the network from those
    papers alone. That turns a meaningless hairball of unrelated pairs into a
    specific answer: *which research community is producing this pattern?* -
    the mining result and the social network, joined in one query.
    """
    items = [s for s in (itemset or "").split(" | ") if s]
    if items:
        marks = ",".join("?" for _ in items)
        scope = f"""
            SELECT wt.work_id
            FROM work_topics wt
            JOIN topics t ON t.topic_id = wt.topic_id
            JOIN works  w ON w.work_id  = wt.work_id
            WHERE w.pub_year BETWEEN ? AND ?
              AND t.display_name IN ({marks})
            GROUP BY wt.work_id
            HAVING COUNT(DISTINCT t.display_name) = {len(items)}
        """
        params = [y0, y1] + items + [min_papers, limit]
    else:
        scope = "SELECT work_id FROM works WHERE pub_year BETWEEN ? AND ?"
        params = [y0, y1, min_papers, limit]

    return db.df(f"""
        WITH scope AS ({scope})
        SELECT a1.display_name AS author_a, a2.display_name AS author_b,
               COUNT(*) AS papers
        FROM work_authors x
        JOIN scope s ON s.work_id = x.work_id
        JOIN work_authors y ON y.work_id = x.work_id AND y.author_id > x.author_id
        JOIN authors a1 ON a1.author_id = x.author_id
        JOIN authors a2 ON a2.author_id = y.author_id
        GROUP BY a1.display_name, a2.display_name
        HAVING COUNT(*) >= ?
        ORDER BY papers DESC
        LIMIT ?
    """, params)


def largest_component(edges: pd.DataFrame) -> pd.DataFrame:
    """
    Keep only the biggest connected group of authors.

    A raw "top 600 pairs" query returns hundreds of unconnected two-person
    islands, which looks like confetti and says nothing. The largest connected
    component is the part of the network that is actually a community.

    Implemented with union-find so it works without networkx installed.
    """
    if edges.empty:
        return edges
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in edges[["author_a", "author_b"]].itertuples(index=False, name=None):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    root = edges["author_a"].map(find)
    return edges[root == root.value_counts().idxmax()].reset_index(drop=True)


def layout_graph(edges: pd.DataFrame, seed=1, iterations=60):
    """
    Give every author an (x, y) position so the graph can be drawn.

    Uses networkx spring layout when available. If networkx is missing we fall
    back to a small force-directed layout written here, so the app never breaks.
    """
    if edges.empty:
        return {}, []
    pairs = list(edges[["author_a", "author_b"]].itertuples(index=False, name=None))
    try:
        import networkx as nx
        g = nx.Graph()
        g.add_weighted_edges_from([(a, b, int(w)) for (a, b), w in
                                   zip(pairs, edges["papers"])])
        pos = nx.spring_layout(g, seed=seed, iterations=iterations)
        return {k: (float(v[0]), float(v[1])) for k, v in pos.items()}, pairs
    except ModuleNotFoundError:
        pass

    nodes = sorted({n for p in pairs for n in p})
    idx = {n: i for i, n in enumerate(nodes)}
    rng = np.random.default_rng(seed)
    pos = rng.normal(0, 1, size=(len(nodes), 2))
    e = np.array([[idx[a], idx[b]] for a, b in pairs])
    for step in range(iterations):
        disp = np.zeros_like(pos)
        d = pos[e[:, 0]] - pos[e[:, 1]]                       # attraction
        np.add.at(disp, e[:, 0], -0.1 * d)
        np.add.at(disp, e[:, 1], 0.1 * d)
        centre = pos - pos.mean(axis=0)                       # repulsion
        disp += 0.02 * centre / (np.linalg.norm(centre, axis=1, keepdims=True) ** 2 + 1e-6)
        pos += disp * (1.0 - step / iterations)
    return {n: (float(pos[i, 0]), float(pos[i, 1])) for n, i in idx.items()}, pairs


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/openalex.duckdb")
    args = ap.parse_args()
    db = DB(args.db)
    lo, hi = year_range(db)
    print(f"engine={db.kind} years={lo}-{hi}")

    w = windows(db)
    print(f"windows: {len(w)} rows"); print(w.head(3).to_string(index=False))
    print("\ncorpus_summary:")
    print(corpus_summary(db).to_string(index=False))
    y0 = int(w.window_start.iloc[-1]); y1 = int(w.window_end.iloc[-1])

    print(f"\ntopic_distribution({y0},{y1}):")
    print(topic_distribution(db, y0, y1, 5).to_string(index=False))
    print(f"\npatterns_for_window({y0}):")
    print(patterns_for_window(db, y0, 2, 5).to_string(index=False))
    picks = patterns_for_window(db, y0, 2, 3)["itemset"].tolist()
    ts = pattern_timeseries(db, picks)
    print(f"\npattern_timeseries: {len(ts)} rows "
          f"({ts.itemset.nunique()} patterns x {len(w)} windows, zeros filled)")
    if picks:
        print(f"  short_label: {short_label(picks[0])}")
    print(f"cooccurrence_matrix: {cooccurrence_matrix(db, y0, y1).shape}")
    print(f"top_rules: {len(top_rules(db, y0))} rows")

    ed = coauthor_edges(db, y0, y1)
    print(f"coauthor_edges (whole window): {len(ed)} rows")
    big = largest_component(ed)
    print(f"  largest_component: {len(big)} edges, "
          f"{len(set(big.author_a) | set(big.author_b)) if not big.empty else 0} authors")
    if picks:
        focused = coauthor_edges(db, y0, y1, 1, 800, picks[0])
        print(f"coauthor_edges (papers behind '{short_label(picks[0])}'): "
              f"{len(focused)} rows")
        pos, pairs = layout_graph(largest_component(focused))
        print(f"layout_graph on that community: {len(pos)} nodes, {len(pairs)} edges")
    pos, pairs = layout_graph(ed)
    print(f"layout_graph: {len(pos)} nodes, {len(pairs)} edges")
    db.close()
    print("\nanalytics self-test OK")

