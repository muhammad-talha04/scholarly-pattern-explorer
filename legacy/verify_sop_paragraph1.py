"""Check every factual claim in paragraph 1 of the personal statement, one by one.

Run from the project folder:  python verify_sop_paragraph1.py
"""
from collections import Counter

import duckdb
import networkx as nx
from networkx.algorithms import community as nxc

DB = "data/canada.duckdb"
YEARS = (2020, 2022)
TOPICS = ["Quantum Computing Algorithms and Architecture",
          "Quantum Information and Cryptography"]
BLAIS, HARRIS, AMIN = "Alexandre Blais", "R. Harris", "M. H. S. Amin"
SEEDS = range(20)

con = duckdb.connect(DB, read_only=True)


def header(n, text):
    print(f"\n[{n}] {text}")


# ---------------------------------------------------------------- claim 1
header(1, "'While mining 44,047 Canadian computer-science papers'")
total = con.execute("SELECT COUNT(*) FROM works").fetchone()[0]
print(f"    papers in canada.duckdb: {total:,}")

# ---------------------------------------------------------------- claim 2
header(2, "'2020 to 2022 papers that paired quantum computing with quantum information'")
scope_sql = """
    SELECT wt.work_id FROM work_topics wt
    JOIN topics t ON t.topic_id = wt.topic_id
    JOIN works  w ON w.work_id  = wt.work_id
    WHERE w.pub_year BETWEEN ? AND ? AND t.display_name IN (?, ?)
    GROUP BY wt.work_id HAVING COUNT(DISTINCT t.display_name) = 2
"""
params = [*YEARS, *TOPICS]
n_papers = con.execute(f"SELECT COUNT(*) FROM ({scope_sql})", params).fetchone()[0]
print(f"    papers with BOTH topics in {YEARS[0]}-{YEARS[1]}: {n_papers:,}")

pairs = con.execute(f"""
    WITH scope AS ({scope_sql})
    SELECT a1.display_name, a2.display_name
    FROM work_authors x
    JOIN scope s ON s.work_id = x.work_id
    JOIN work_authors y ON y.work_id = x.work_id AND y.author_id > x.author_id
    JOIN authors a1 ON a1.author_id = x.author_id
    JOIN authors a2 ON a2.author_id = y.author_id
    GROUP BY 1, 2
""", params).fetchall()
graph = nx.Graph(pairs)
graph.remove_edges_from(nx.selfloop_edges(graph))
largest = graph.subgraph(max(nx.connected_components(graph), key=len)).copy()
print(f"    co-author graph: {graph.number_of_nodes():,} authors; "
      f"largest connected part: {largest.number_of_nodes():,} authors, "
      f"{largest.number_of_edges():,} links")

# ---------------------------------------------------------------- claim 3
header(3, "'Louvain community detection split it into groups' (and is the split stable?)")
communities = nxc.louvain_communities(largest, seed=1)
sizes = sorted((len(c) for c in communities), reverse=True)
print(f"    seed 1: {len(communities)} communities, largest sizes {sizes[:8]}")

same_group, cross_links = 0, []
for seed in SEEDS:
    parts = nxc.louvain_communities(largest, seed=seed)
    lab = {a: i for i, grp in enumerate(parts) for a in grp}
    if lab[BLAIS] == lab[HARRIS]:
        same_group += 1
    cross_links.append(sum(1 for u, v in largest.edges
                           if {lab[u], lab[v]} == {lab[BLAIS], lab[HARRIS]}))
print(f"    over {len(SEEDS)} random seeds: Blais and Harris in the SAME community {same_group} times")
print(f"    direct links between their two communities per seed: {cross_links}")

# ---------------------------------------------------------------- claim 4
header(4, "'One formed around Alexandre Blais in Sherbrooke; the other was D-Wave's hardware "
          "team, including R. Harris and M. H. S. Amin'")
label = {a: i for i, grp in enumerate(communities) for a in grp}
inst = dict(con.execute("SELECT display_name, ANY_VALUE(institution) FROM authors GROUP BY 1").fetchall())
for name in (BLAIS, HARRIS, AMIN):
    grp = communities[label[name]]
    top = Counter(inst.get(a) or "unknown" for a in grp).most_common(3)
    hub = max(grp, key=largest.degree)
    print(f"    {name}: community of {len(grp)}; own institution = {inst.get(name)}")
    print(f"        most connected member: {hub} ({largest.degree[hub]} links)")
    print(f"        top institutions in this community: {top}")
print(f"    Harris and Amin in the same community: {label[HARRIS] == label[AMIN]}")
print("    NOTE: institution is read here only to CHECK the result; the community "
      "detection above used co-author pairs alone.")

# ---------------------------------------------------------------- claim 5
header(5, "'the two groups shared no direct co-authorship link'")
cross = [(u, v) for u, v in largest.edges if {label[u], label[v]} == {label[BLAIS], label[HARRIS]}]
print(f"    links between the two communities (seed 1): {len(cross)}")
print(f"    did Blais and Harris ever co-author directly? {largest.has_edge(BLAIS, HARRIS)}")

# ---------------------------------------------------------------- claim 6
header(6, "'The shortest path from Blais to Harris ran through four collaborations'")
path = nx.shortest_path(largest, BLAIS, HARRIS)
print(f"    {len(path) - 1} steps: " + " -> ".join(path))
print(f"    number of different shortest paths of that length: "
      f"{sum(1 for _ in nx.all_shortest_paths(largest, BLAIS, HARRIS))}")
for a, b in zip(path, path[1:]):
    row = con.execute(f"""
        WITH scope AS ({scope_sql})
        SELECT w.work_id, w.pub_year, w.title FROM works w
        JOIN scope s ON s.work_id = w.work_id
        JOIN work_authors x ON x.work_id = w.work_id JOIN authors ax ON ax.author_id = x.author_id
        JOIN work_authors y ON y.work_id = w.work_id JOIN authors ay ON ay.author_id = y.author_id
        WHERE ax.display_name = ? AND ay.display_name = ?
        LIMIT 1
    """, params + [a, b]).fetchone()
    print(f"    {a} + {b}: {row[1]}  {row[2][:70]}")
    print(f"        open it: https://openalex.org/{row[0].rsplit('/', 1)[-1]}")
