"""Stratified galaxy samples and the in-process galaxy cache."""
from collections import Counter

from ml.galaxy import _quotas, sample_graph
from ml.service import MLService, SummaryCache
from ml.store import LocalStore


def _graph(sizes):
    nodes, links = [], []
    for c, n in sizes.items():
        for i in range(n):
            nodes.append({"id": f"{c}-{i}", "topic_id": "t", "topic_name": f"{c}-{i}",
                          "x": 0.0, "y": 0.0, "z": 0.0, "cluster_id": c, "cluster_label": c,
                          "year": 2020 + i % 6, "support": round(1 / (i + 1), 4)})
    for a, b in zip(nodes, nodes[1:]):
        links.append({"source": a["topic_name"], "target": b["topic_name"], "weight": 0.5})
    clusters = [{"id": c, "name": c, "label": c, "centroid": {"x": 0, "y": 0, "z": 0}, "size": n}
                for c, n in sizes.items()]
    return {"nodes": nodes, "clusters": clusters, "links": links}


SIZES = {"a": 700, "b": 250, "c": 45, "d": 5}


def test_quotas_proportional_with_minimum():
    q = _quotas(SIZES, 100, 3)
    assert sum(q.values()) == 100 and min(q.values()) >= 3
    assert q["a"] > q["b"] > q["c"] >= q["d"] == 3
    assert _quotas({"a": 10, "b": 5}, 4, 3) == {"a": 3, "b": 1}   # minimum can't fit everyone


def test_sample_is_stratified_deterministic_and_well_formed():
    g = _graph(SIZES)
    s = sample_graph(g, 100)
    assert len(s["nodes"]) == 100 and s == sample_graph(_graph(SIZES), 100)
    per = Counter(n["cluster_id"] for n in s["nodes"])
    assert set(per) == set(SIZES) and per["a"] > per["b"]        # a prefix cap would be all "a"
    # most-cited first inside each cluster
    assert {n["id"] for n in s["nodes"] if n["cluster_id"] == "d"} == {"d-0", "d-1", "d-2"}
    names = {n["topic_name"] for n in s["nodes"]}
    assert s["links"] and all(e["source"] in names and e["target"] in names for e in s["links"])
    assert s["clusters"] == g["clusters"] and set(s) == {"nodes", "clusters", "links"}
    assert sample_graph(g, 10_000) is g


def _svc(tmp_path):
    return MLService(store=LocalStore(), cache=SummaryCache(":memory:"), galaxy_dir=tmp_path)


def test_galaxy_doc_is_parsed_once_within_ttl(tmp_path, monkeypatch):
    svc = _svc(tmp_path)
    svc.store.put_document("galaxy", _graph({"a": 20}))
    calls = Counter()
    real = svc.store.get_document
    monkeypatch.setattr(svc.store, "get_document", lambda k: (calls.update([k]), real(k))[1])
    for _ in range(5):
        assert len(svc.read_galaxy()["nodes"]) == 20
    assert calls["galaxy"] == 1
    monkeypatch.setenv("GALAXY_CACHE_TTL", "0")
    svc.read_galaxy()
    assert calls["galaxy"] == 2


def test_small_limits_use_stored_sample_without_full_doc(tmp_path, monkeypatch):
    svc = _svc(tmp_path)
    full = _graph(SIZES)
    svc.store.put_document("galaxy", full)
    svc.store.put_document("galaxy_sample", sample_graph(full, 600))
    seen = []
    real = svc.store.get_document
    monkeypatch.setattr(svc.store, "get_document", lambda k: (seen.append(k), real(k))[1])
    out = svc.read_galaxy(310)
    assert len(out["nodes"]) == 310 and "galaxy" not in seen
    assert len(svc.read_galaxy(800)["nodes"]) == 800 and "galaxy" in seen   # falls back


def test_rebuild_stores_hero_sample(tmp_path, monkeypatch):
    monkeypatch.setenv("ML_EMBEDDER", "hash")
    from ml.papers import Paper
    svc = _svc(tmp_path)
    svc.index_papers([Paper(work_id=f"W{i}", title=f"topic {i % 4} graph", abstract="x")
                      for i in range(12)])
    svc.read_galaxy()                      # warm the cache with the empty graph
    graph = svc.rebuild_galaxy()
    assert svc.store.get_document("galaxy_sample")["nodes"] == graph["nodes"]  # 12 < 600
    assert len(svc.read_galaxy()["nodes"]) == 12                                # cache cleared


def test_legacy_galaxy_without_color_index_is_backfilled(tmp_path, monkeypatch):
    from ml.galaxy import ensure_color_index
    legacy = {"nodes": [{"id": "a", "cluster_id": "2"}, {"id": "b", "cluster_id": "-1"},
                        {"id": "c", "cluster_id": "1", "color_index": 7}],
              "clusters": [{"id": "2"}, {"id": "-1"}], "links": []}
    out = ensure_color_index(legacy)
    assert [n["color_index"] for n in out["nodes"]] == [2, -1, 7]
    assert [c["color_index"] for c in out["clusters"]] == [2, -1]
