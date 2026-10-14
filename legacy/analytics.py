"""
STEP 4a: every database question the web app needs, in one tested place.

The app (app.py) contains NO SQL. It only calls functions from here. That split
matters: this file can be tested from the command line, a Streamlit app cannot.

COUNTRY SCOPE
-------------
Almost every function takes `country=None`.
  None  -> the whole corpus (tables: patterns, rules)
  "PK"  -> only papers with at least one author at a Pakistani institution
           (tables: work_countries, country_patterns, country_rules)

Self-test:  python analytics.py --db data/openalex.duckdb
            python analytics.py --db data/openalex.duckdb --country CA
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from dbconn import DB


# ----------------------------------------------------------------- helpers ----

def has_table(db, name: str) -> bool:
    try:
        db.df(f"SELECT 1 FROM {name} LIMIT 1")
        return True
    except Exception:                                          # noqa: BLE001
        return False


def _in_country(country, alias="w"):
    """SQL fragment + params restricting `alias.work_id` to one country."""
    if not country:
        return "", []
    return (f" AND {alias}.work_id IN (SELECT work_id FROM work_countries "
            f"WHERE country = ?)"), [country]


def _pattern_source(country, table="patterns"):
    """('patterns', '', []) or ('country_patterns', 'country = ? AND', ['PK'])."""
    if not country:
        return table, "", []
    return f"country_{table}", "country = ? AND", [country]


# ---------------------------------------------------------------- overview ----

def year_range(db):
    r = db.df("SELECT MIN(pub_year) AS lo, MAX(pub_year) AS hi FROM works")
    return int(r.lo[0]), int(r.hi[0])


def windows(db, country=None) -> pd.DataFrame:
    table, cond, params = _pattern_source(country)
    if country and not has_table(db, table):
        return pd.DataFrame(columns=["window_start", "window_end", "papers", "itemsets"])
    return db.df(f"""
        SELECT window_start, window_end, MAX(n_tx) AS papers, COUNT(*) AS itemsets
        FROM {table} WHERE {cond} TRUE
        GROUP BY window_start, window_end ORDER BY window_start
    """, params)


def corpus_summary(db, country=None) -> pd.DataFrame:
    """One row of headline counts, for the whole corpus or one country."""
    if not country:
        return db.df("""
            SELECT (SELECT COUNT(*) FROM works)    AS works,
                   (SELECT COUNT(*) FROM topics)   AS topics,
                   (SELECT COUNT(*) FROM authors)  AS authors,
                   (SELECT COUNT(*) FROM patterns) AS patterns,
                   (SELECT COUNT(*) FROM rules)    AS rules
        """)
    has_cp = has_table(db, "country_patterns")
    return db.df(f"""
        WITH scope AS (SELECT work_id FROM work_countries WHERE country = ?)
        SELECT (SELECT COUNT(*) FROM scope) AS works,
               (SELECT COUNT(DISTINCT wt.topic_id) FROM work_topics wt
                  JOIN scope s ON s.work_id = wt.work_id) AS topics,
               (SELECT COUNT(DISTINCT wa.author_id) FROM work_authors wa
                  JOIN scope s ON s.work_id = wa.work_id) AS authors,
               {"(SELECT COUNT(*) FROM country_patterns WHERE country = ?)" if has_cp else "0"} AS patterns,
               {"(SELECT COUNT(*) FROM country_rules WHERE country = ?)" if has_cp else "0"} AS rules
    """, [country] + ([country, country] if has_cp else []))


def country_list(db) -> pd.DataFrame:
    """Every country in the corpus with its paper count, biggest first.
    `mined` says whether mine_countries.py produced patterns for it."""
    if not has_table(db, "work_countries"):
        return pd.DataFrame(columns=["country", "papers", "mined"])
    mined = "FALSE"
    if has_table(db, "country_patterns"):
        mined = ("wc.country IN (SELECT DISTINCT country FROM country_patterns)")
    return db.df(f"""
        SELECT wc.country, COUNT(*) AS papers, {mined} AS mined
        FROM work_countries wc
        GROUP BY wc.country
        ORDER BY papers DESC
    """)


def papers_per_year(db, country=None) -> pd.DataFrame:
    extra, params = _in_country(country)
    return db.df(f"""
        SELECT w.pub_year AS year, COUNT(*) AS papers
        FROM works w WHERE TRUE {extra}
        GROUP BY w.pub_year ORDER BY w.pub_year
    """, params)


# ---------------------------------------------------------------- raw data ----

def topic_distribution(db, y0, y1, limit=20, country=None) -> pd.DataFrame:
    """VIEW 1 - the raw data: how often does each topic appear in this window?"""
    extra, params = _in_country(country)
    return db.df(f"""
        SELECT t.display_name AS topic, t.field, COUNT(*) AS papers
        FROM work_topics wt
        JOIN topics t ON t.topic_id = wt.topic_id
        JOIN works  w ON w.work_id  = wt.work_id
        WHERE w.pub_year BETWEEN ? AND ? {extra}
        GROUP BY t.display_name, t.field
        ORDER BY papers DESC
        LIMIT ?
    """, [y0, y1] + params + [limit])


def cooccurrence_matrix(db, y0, y1, top_n=12, country=None) -> pd.DataFrame:
    """A topic-by-topic count table, built with a SELF JOIN on the bridge table."""
    top = topic_distribution(db, y0, y1, top_n, country)["topic"].tolist()
    if len(top) < 2:
        return pd.DataFrame()
    extra, params = _in_country(country)
    marks = ",".join("?" for _ in top)
    pairs = db.df(f"""
        SELECT a.display_name AS topic_a, b.display_name AS topic_b, COUNT(*) AS papers
        FROM work_topics wa
        JOIN work_topics wb ON wb.work_id = wa.work_id AND wb.topic_id <> wa.topic_id
        JOIN topics a ON a.topic_id = wa.topic_id
        JOIN topics b ON b.topic_id = wb.topic_id
        JOIN works  w ON w.work_id  = wa.work_id
        WHERE w.pub_year BETWEEN ? AND ? {extra}
          AND a.display_name IN ({marks}) AND b.display_name IN ({marks})
        GROUP BY a.display_name, b.display_name
    """, [y0, y1] + params + top + top)
    if pairs.empty:
        return pd.DataFrame()
    return pairs.pivot(index="topic_a", columns="topic_b", values="papers").fillna(0)


# ----------------------------------------------------------------- patterns ----

def patterns_for_window(db, y0, min_k=2, limit=40, country=None) -> pd.DataFrame:
    """VIEW 2 - the mining results for one window."""
    table, cond, params = _pattern_source(country)
    if country and not has_table(db, table):
        return pd.DataFrame(columns=["itemset", "k", "support_count", "n_tx", "support"])
    return db.df(f"""
        SELECT itemset, k, support_count, n_tx, support
        FROM {table}
        WHERE {cond} window_start = ? AND k >= ?
        ORDER BY support DESC
        LIMIT ?
    """, params + [y0, min_k, limit])


def pattern_timeseries(db, itemsets: list[str], country=None) -> pd.DataFrame:
    """
    VIEW 3 - the same patterns tracked across every window.

    A pattern that was not frequent in a window has NO ROW in the patterns
    table, so missing windows are filled with support 0: the line visibly
    climbs from zero, which is the actual claim being made.
    """
    empty = pd.DataFrame(columns=["itemset", "window_start", "support"])
    if not itemsets:
        return empty
    table, cond, params = _pattern_source(country)
    marks = ",".join("?" for _ in itemsets)
    found = db.df(f"""
        SELECT itemset, window_start, support
        FROM {table}
        WHERE {cond} itemset IN ({marks})
        ORDER BY itemset, window_start
    """, params + list(itemsets))
    if found.empty:
        return empty

    all_windows = db.df(f"SELECT DISTINCT window_start FROM {table} WHERE {cond} TRUE "
                        "ORDER BY window_start", params)["window_start"].tolist()
    grid = pd.MultiIndex.from_product(
        [sorted(found["itemset"].unique()), all_windows],
        names=["itemset", "window_start"],
    )
    return (found.set_index(["itemset", "window_start"])
                 .reindex(grid, fill_value=0.0)
                 .reset_index())


def emerging_declining(db, top=10, country=None):
    """Patterns whose support grew / fell most between first and last window."""
    table, cond, params = _pattern_source(country)
    if country and not has_table(db, table):
        e = pd.DataFrame()
        return e, e
    df = db.df(f"""
        WITH ranked AS (
            SELECT itemset, window_start, support,
                   ROW_NUMBER() OVER (PARTITION BY itemset ORDER BY window_start)      AS rn_first,
                   ROW_NUMBER() OVER (PARTITION BY itemset ORDER BY window_start DESC) AS rn_last
            FROM {table} WHERE {cond} k >= 2
        )
        SELECT f.itemset,
               f.window_start AS first_window, f.support AS first_support,
               l.window_start AS last_window,  l.support AS last_support,
               l.support - f.support AS change
        FROM ranked f JOIN ranked l
          ON l.itemset = f.itemset AND f.rn_first = 1 AND l.rn_last = 1
        ORDER BY change DESC
    """, params)
    if df.empty:
        return df, df
    return df.head(top).reset_index(drop=True), df.tail(top).iloc[::-1].reset_index(drop=True)


def short_label(itemset: str, per_item: int = 20) -> str:
    """Squeeze 'A very long topic name | Another long one' for a chart legend."""
    parts = [p if len(p) <= per_item else p[:per_item - 1] + "…"
             for p in itemset.split(" | ")]
    return " + ".join(parts)


def top_rules(db, y0, min_lift=1.1, limit=25, country=None) -> pd.DataFrame:
    table, cond, params = _pattern_source(country, "rules")
    if country and not has_table(db, table):
        return pd.DataFrame(columns=["antecedent", "consequent", "support",
                                     "confidence", "lift"])
    return db.df(f"""
        SELECT antecedent, consequent, support, confidence, lift
        FROM {table}
        WHERE {cond} window_start = ? AND lift >= ?
        ORDER BY lift DESC
        LIMIT ?
    """, params + [y0, min_lift, limit])


# ------------------------------------------------------------ co-authorship ----

def coauthor_edges(db, y0, y1, min_papers=2, limit=600, itemset=None,
                   country=None, local_only=False) -> pd.DataFrame:
    """
    VIEW 4 - the social network. Two authors are linked if they co-wrote papers.

    itemset    : only papers containing EVERY topic of that pattern
    country    : only papers with an author from that country
    local_only : additionally keep only authors based in that country
    """
    items = [s for s in (itemset or "").split(" | ") if s]
    c_extra, c_params = _in_country(country)
    if items:
        marks = ",".join("?" for _ in items)
        scope = f"""
            SELECT wt.work_id
            FROM work_topics wt
            JOIN topics t ON t.topic_id = wt.topic_id
            JOIN works  w ON w.work_id  = wt.work_id
            WHERE w.pub_year BETWEEN ? AND ? {c_extra}
              AND t.display_name IN ({marks})
            GROUP BY wt.work_id
            HAVING COUNT(DISTINCT t.display_name) = {len(items)}
        """
        scope_params = [y0, y1] + c_params + items
    else:
        scope = f"SELECT w.work_id FROM works w WHERE w.pub_year BETWEEN ? AND ? {c_extra}"
        scope_params = [y0, y1] + c_params

    local = ""
    local_params: list = []
    if country and local_only:
        local = "AND a1.country = ? AND a2.country = ?"
        local_params = [country, country]

    return db.df(f"""
        WITH scope AS ({scope})
        SELECT a1.display_name AS author_a, a2.display_name AS author_b,
               COUNT(*) AS papers,
               MAX(a1.country) AS country_a, MAX(a2.country) AS country_b
        FROM work_authors x
        JOIN scope s ON s.work_id = x.work_id
        JOIN work_authors y ON y.work_id = x.work_id AND y.author_id > x.author_id
        JOIN authors a1 ON a1.author_id = x.author_id
        JOIN authors a2 ON a2.author_id = y.author_id
        WHERE TRUE {local}
        GROUP BY a1.display_name, a2.display_name
        HAVING COUNT(*) >= ?
        ORDER BY papers DESC
        LIMIT ?
    """, scope_params + local_params + [min_papers, limit])


def largest_component(edges: pd.DataFrame) -> pd.DataFrame:
    """
    Keep only the biggest connected group of authors (union-find, no networkx).
    A raw "top 600 pairs" query returns hundreds of two-person islands.
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
    Uses networkx spring layout when available, else a small built-in one.
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


def network(db, y0, y1, min_papers=2, limit=800, itemset=None, country=None,
            local_only=False, only_big=True) -> dict:
    """Edges + layout + degrees in ONE call, so the app can cache the whole
    (slow) spring layout instead of recomputing it on every click."""
    edges = coauthor_edges(db, y0, y1, min_papers, limit, itemset, country, local_only)
    if only_big:
        edges = largest_component(edges)
    pos, pairs = layout_graph(edges)
    degree: dict[str, int] = {}
    home: dict[str, str] = {}
    for r in edges.itertuples(index=False):
        degree[r.author_a] = degree.get(r.author_a, 0) + 1
        degree[r.author_b] = degree.get(r.author_b, 0) + 1
        home.setdefault(r.author_a, r.country_a if isinstance(r.country_a, str) else "")
        home.setdefault(r.author_b, r.country_b if isinstance(r.country_b, str) else "")
    return {"edges": edges, "pos": pos, "pairs": pairs, "degree": degree, "home": home}


# ------------------------------------------------------------------- world ----

def country_papers(db, y0=None, y1=None) -> pd.DataFrame:
    """Papers per country, optionally inside one window (for the world map)."""
    if not has_table(db, "work_countries"):
        return pd.DataFrame(columns=["country", "papers"])
    where, params = "", []
    if y0 is not None:
        where, params = "WHERE w.pub_year BETWEEN ? AND ?", [y0, y1]
    return db.df(f"""
        SELECT wc.country, COUNT(*) AS papers
        FROM work_countries wc JOIN works w ON w.work_id = wc.work_id
        {where}
        GROUP BY wc.country ORDER BY papers DESC
    """, params)


def collaboration_partners(db, country, y0=None, y1=None, limit=15) -> pd.DataFrame:
    """Countries that co-wrote the most papers with `country`."""
    where, params = "", []
    if y0 is not None:
        where, params = "AND w.pub_year BETWEEN ? AND ?", [y0, y1]
    return db.df(f"""
        SELECT b.country AS partner, COUNT(*) AS papers
        FROM work_countries a
        JOIN work_countries b ON b.work_id = a.work_id AND b.country <> a.country
        JOIN works w ON w.work_id = a.work_id
        WHERE a.country = ? {where}
        GROUP BY b.country ORDER BY papers DESC LIMIT ?
    """, [country] + params + [limit])


def top_country_pairs(db, y0=None, y1=None, limit=15) -> pd.DataFrame:
    """The strongest international collaboration pairs in the corpus."""
    where, params = "", []
    if y0 is not None:
        where, params = "AND w.pub_year BETWEEN ? AND ?", [y0, y1]
    return db.df(f"""
        SELECT a.country AS country_a, b.country AS country_b, COUNT(*) AS papers
        FROM work_countries a
        JOIN work_countries b ON b.work_id = a.work_id AND b.country > a.country
        JOIN works w ON w.work_id = a.work_id
        WHERE TRUE {where}
        GROUP BY a.country, b.country ORDER BY papers DESC LIMIT ?
    """, params + [limit])


def international_share(db, country=None) -> pd.DataFrame:
    """Share of papers per year that involve more than one country."""
    extra, params = _in_country(country)
    return db.df(f"""
        WITH n AS (SELECT work_id, COUNT(*) AS c FROM work_countries GROUP BY work_id)
        SELECT w.pub_year AS year,
               AVG(CASE WHEN n.c > 1 THEN 1.0 ELSE 0.0 END) AS share,
               COUNT(*) AS papers
        FROM works w JOIN n ON n.work_id = w.work_id
        WHERE TRUE {extra}
        GROUP BY w.pub_year ORDER BY w.pub_year
    """, params)


# ---------------------------------------------------------- link prediction ----

def link_metrics(db) -> pd.DataFrame:
    if not has_table(db, "link_metrics"):
        return pd.DataFrame(columns=["model", "auc", "ap"])
    return db.df("SELECT model, auc, ap FROM link_metrics ORDER BY auc DESC")


def link_predictions(db, country=None, limit=300) -> pd.DataFrame:
    if not has_table(db, "link_predictions"):
        return pd.DataFrame(columns=["author_a", "country_a", "author_b",
                                     "country_b", "score"])
    where, params = "", []
    if country:
        where, params = "WHERE a1.country = ? OR a2.country = ?", [country, country]
    return db.df(f"""
        SELECT a1.display_name AS author_a, a1.country AS country_a,
               a2.display_name AS author_b, a2.country AS country_b,
               p.score
        FROM link_predictions p
        JOIN authors a1 ON a1.author_id = p.author_a
        JOIN authors a2 ON a2.author_id = p.author_b
        {where}
        ORDER BY p.score DESC LIMIT ?
    """, params + [limit])


# --------------------------------------------------------------- self-test ----

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/openalex.duckdb")
    ap.add_argument("--country", default=None)
    args = ap.parse_args()
    db = DB(args.db, read_only=True)
    c = args.country
    lo, hi = year_range(db)
    print(f"engine={db.kind} years={lo}-{hi} country={c or 'ALL'}")

    w = windows(db, c)
    print(f"windows: {len(w)} rows")
    print(corpus_summary(db, c).to_string(index=False))
    print(f"countries: {len(country_list(db))}")
    if w.empty:
        raise SystemExit("no windows for this scope (run mine_countries.py?)")
    y0 = int(w.window_start.iloc[-1]); y1 = int(w.window_end.iloc[-1])
    print(topic_distribution(db, y0, y1, 5, c).to_string(index=False))
    picks = patterns_for_window(db, y0, 2, 3, c)["itemset"].tolist()
    print(f"patterns: {picks}")
    print(f"timeseries rows: {len(pattern_timeseries(db, picks, c))}")
    print(f"cooccurrence: {cooccurrence_matrix(db, y0, y1, 12, c).shape}")
    print(f"rules: {len(top_rules(db, y0, 1.1, 25, c))}")
    e, d = emerging_declining(db, 5, c)
    print(f"emerging: {len(e)}  declining: {len(d)}")
    net = network(db, y0, y1, 2, 800, None, c)
    print(f"network: {len(net['pos'])} nodes, {len(net['pairs'])} edges")
    print(f"country papers: {len(country_papers(db, y0, y1))}")
    print(f"pairs: {len(top_country_pairs(db))}")
    if c:
        print(f"partners: {len(collaboration_partners(db, c))}")
    print(f"intl share rows: {len(international_share(db, c))}")
    print(f"link preds: {len(link_predictions(db, c))}")
    db.close()
    print("\nanalytics self-test OK")
