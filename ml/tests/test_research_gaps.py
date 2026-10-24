import json

import numpy as np

from ml.research_gaps import (examples_for_topics, examples_from_works, find_semantic_gaps,
                              semantic_gaps_from_store)
from ml.store import LocalStore


def _u(*xs):
    v = np.zeros(8, dtype=np.float32)
    for i, x in enumerate(xs):
        v[i] = x
    return v / np.linalg.norm(v)


def _corpus():
    """Related literatures that rarely meet, a thin neighbour, and a pair that already co-occurs."""
    papers, vecs = [], []

    def add(wid, topics, vec, year):
        papers.append({"work_id": wid, "title": f"Paper {wid}", "pub_year": year, "topics": topics})
        vecs.append(vec)

    alpha, beta = _u(1, 0), _u(1, 0.05)
    thin = _u(1, 0)
    together = _u(0, 1)
    east, west = _u(0, 0, 1), _u(0, 0, 0, 1)
    for i in range(6):
        add(f"A{i}", ["Alpha"], alpha, 2022 + i % 3)
        add(f"B{i}", ["Beta"], beta, 2023)
        add(f"G{i}", ["Gamma", "Delta"], together, 2024)
        add(f"E{i}", ["Epsilon"], east, 2021)
        add(f"Z{i}", ["Zeta"], west, 2024)
    add("T0", ["Thin"], thin, 2022)
    add("T1", ["Thin"], thin, 2024)
    return papers, np.stack(vecs)


def test_related_topics_with_low_cooccurrence_rank_first():
    papers, vecs = _corpus()
    gaps = find_semantic_gaps(papers, vecs, min_sim=0.9, min_each=5, max_co_rate=0.2,
                              min_neighbor=5, max_density_ratio=0.5)
    assert gaps
    top = gaps[0]
    assert top["kind"] == "cooccurrence"
    assert top["items"] == ["Alpha", "Beta"]
    assert top["paper_count"] == 0
    assert "Alpha" in top["explanation"] and "Beta" in top["explanation"]
    assert "together" in top["explanation"]
    ids = {e["id"] for e in top["example_papers"]}
    assert ids and ids <= {p["work_id"] for p in papers}
    assert top["window_start"] == 2021 and top["window_end"] == 2024
    assert all(g["gap_score"] >= gaps[i + 1]["gap_score"] for i, g in enumerate(gaps[:-1]))


def test_topics_that_already_cooccur_are_not_gaps():
    papers, vecs = _corpus()
    gaps = find_semantic_gaps(papers, vecs, min_sim=0.9, min_each=5, min_neighbor=5)
    items = {tuple(g["items"]) for g in gaps}
    assert ("Gamma", "Delta") not in items and ("Delta", "Gamma") not in items
    assert ("Epsilon", "Zeta") not in items


def test_thin_topic_beside_busy_neighbors():
    papers, vecs = _corpus()
    gaps = find_semantic_gaps(papers, vecs, min_sim=0.9, min_each=5, min_neighbor=5,
                              max_density_ratio=0.5)
    thin = next(g for g in gaps if g["items"] == ["Thin"])
    assert thin["kind"] == "density"
    assert thin["paper_count"] == 2
    assert "Thin" in thin["explanation"] and "Alpha" in thin["explanation"]
    assert {e["id"] for e in thin["example_papers"]} <= {"T0", "T1"}
    assert {e["id"] for e in thin["example_papers"]} & {"T0", "T1"}


def test_examples_from_works_prefers_recent_papers(tmp_path):
    path = tmp_path / "works_v2.jsonl"
    rows = [
        {"id": "W1", "title": "Older alpha", "year": 2022, "topics": ["Alpha"]},
        {"id": "W2", "title": "Newer alpha", "year": 2025, "topics": ["Alpha", "Beta"]},
        {"id": "W3", "title": "Only beta", "year": 2024, "topics": ["Beta"]},
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows))
    got = examples_from_works(["Alpha", "Beta"], n=3, works_path=path)
    assert [e["id"] for e in got] == ["W2", "W3", "W1"]
    assert got[0]["title"] == "Newer alpha"


def test_store_and_pg_readers(tmp_path):
    store = LocalStore(tmp_path / "v", dim=4)
    vecs = np.array([[1, 0, 0, 0], [1, 0, 0, 0]], dtype=np.float32)
    store.upsert(["W1", "W2"], vecs, [
        {"work_id": "W1", "title": "Red paper", "pub_year": 2024, "topics": ["Red"]},
        {"work_id": "W2", "title": "Blue paper", "pub_year": 2023, "topics": ["Blue"]},
    ])
    assert semantic_gaps_from_store(store) == []  # below the default minimum counts
    found = semantic_gaps_from_store(store, min_each=1, min_sim=0.9, min_neighbor=100)
    assert found[0]["items"] == ["Blue", "Red"]
    assert examples_for_topics(store, ["Red"])[0]["id"] == "W1"

    class Cur:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def execute(self, sql, params=None):
            assert "FROM paper_embeddings" in sql
        def fetchall(self):
            second = {"work_id": "W2", "title": "Blue paper", "pub_year": 2023, "topics": ["Blue"]}
            return [
                ("W1", "[1, 0, 0, 0]",
                 {"work_id": "W1", "title": "Red paper", "pub_year": 2024, "topics": ["Red"]}),
                ("W2", "[1, 0, 0, 0]", json.dumps(second)),
            ]

    class Pg:
        def __len__(self):
            return 2
        def cursor(self):
            return Cur()
        conn = property(lambda self: self)

    # semantic_gaps_from_store looks for .conn.cursor(); give Pg a conn attribute.
    Pg.conn = property(lambda self: self)
    gaps = semantic_gaps_from_store(Pg(), min_each=1, min_sim=0.9, min_neighbor=100)
    assert gaps[0]["items"] == ["Blue", "Red"]
    assert {e["id"] for e in gaps[0]["example_papers"]} == {"W1", "W2"}
