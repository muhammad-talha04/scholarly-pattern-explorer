"""Reproduce the co-authorship claims used in the personal statement and CV.

Run from the project folder:  python verify_quantum_communities.py
Needs: duckdb, networkx (both already used by the project).
"""
import duckdb
import networkx as nx
from networkx.algorithms import community as nxc

DB = "data/canada.duckdb"
YEARS = (2020, 2022)
TOPICS = ["Quantum Computing Algorithms and Architecture",
          "Quantum Information and Cryptography"]

con = duckdb.connect(DB, read_only=True)

print("Link-prediction metrics (model, AUC, AP):")
for row in con.execute("SELECT * FROM link_metrics ORDER BY auc DESC").fetchall():
    print("  ", row)

# Every co-author pair on papers carrying BOTH topics (no row cap, unlike the dashboard).
pairs = con.execute("""
    WITH scope AS (
        SELECT wt.work_id FROM work_topics wt
        JOIN topics t ON t.topic_id = wt.topic_id
        JOIN works  w ON w.work_id  = wt.work_id
        WHERE w.pub_year BETWEEN ? AND ? AND t.display_name IN (?, ?)
        GROUP BY wt.work_id HAVING COUNT(DISTINCT t.display_name) = 2)
    SELECT a1.display_name, a2.display_name
    FROM work_authors x
    JOIN scope s ON s.work_id = x.work_id
    JOIN work_authors y ON y.work_id = x.work_id AND y.author_id > x.author_id
    JOIN authors a1 ON a1.author_id = x.author_id
    JOIN authors a2 ON a2.author_id = y.author_id
    GROUP BY 1, 2
""", [*YEARS, *TOPICS]).fetchall()

graph = nx.Graph(pairs)
largest = graph.subgraph(max(nx.connected_components(graph), key=len)).copy()
print(f"\nLargest component {YEARS}: {largest.number_of_nodes()} authors, "
      f"{largest.number_of_edges()} links")

communities = nxc.louvain_communities(largest, seed=1)
label = {author: i for i, group in enumerate(communities) for author in group}

blais, harris = "Alexandre Blais", "R. Harris"
for name in (blais, harris, "M. H. S. Amin"):
    group = communities[label[name]]
    print(f"{name}: community of {len(group)} authors")

cross = sum(1 for u, v in largest.edges if {label[u], label[v]} == {label[blais], label[harris]})
print("Direct links between the Blais and D-Wave communities:", cross)
path = nx.shortest_path(largest, blais, harris)
print(f"Shortest path ({len(path) - 1} collaborations):", " -> ".join(path))
