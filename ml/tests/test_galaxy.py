import numpy as np

from ml.embeddings import HashEmbedder
from ml.galaxy import (GalaxyMap, cluster_ids, ctfidf_labels, empty_graph, graph_from_layout,
                       knn_links, resolve_method)
from ml.papers import Paper
from ml.service import MLService, SummaryCache
from ml.store import LocalStore


def test_ctfidf_labels_use_distinctive_words():
    labels = [0, 0, 1, 1]
    texts = ["protein folding transformer structure", "protein structure prediction",
             "quantum surface code qubits", "quantum error correction qubits"]
    names = ctfidf_labels(labels, texts, n_terms=2)
    assert "protein" in names[0]
    assert "quantum" in names[1] or "qubits" in names[1]


def test_ctfidf_labels_drop_generic_words():
    labels = [0, 0, 1, 1, 2, 2, 2]
    texts = [
        "ai learning study of multi model data",
        "ai learning study of multi model data systems",
        "quantum model learning qubits data",
        "quantum learning model qubits study",
        "large language models for translation",
        "large language models answer questions",
        "language models at large scale",
    ]
    names = ctfidf_labels(labels, texts, n_terms=3)
    assert names[1] == "quantum, qubits"
    for word in ("ai", "learning", "model", "data", "study", "multi"):
        assert word not in names[1].split(", ")
    assert names[2].split(", ")[0] == "language"
    for word in ("large", "models", "model"):
        assert word not in names[2].split(", ")
    # Every term was generic, so the label falls back instead of going empty.
    assert names[0]
    assert "cluster" not in names[0]


def test_method_falls_back_without_umap(monkeypatch):
    monkeypatch.setattr("ml.galaxy._optional_available", lambda: False)
    assert resolve_method("auto", 100) == "kmeans"
    monkeypatch.setattr("ml.galaxy._optional_available", lambda: True)
    assert resolve_method("auto", 100) == "umap-hdbscan"
    assert resolve_method("auto", 10) == "kmeans"
    labels, method = cluster_ids(np.eye(4, dtype=np.float32), method="umap-hdbscan")
    assert len(labels) == 4 and method in {"kmeans", "umap-hdbscan"}


def _blobs():
    rng = np.random.default_rng(1)
    left = rng.normal(size=(6, 16))
    left[:, 0] += 5
    right = rng.normal(size=(6, 16))
    right[:, 1] += 5
    vectors = np.vstack([left, right]).astype(np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    ids = [f"P{i}" for i in range(12)]
    metas = []
    for i in range(12):
        if i < 6:
            metas.append({"title": "protein folding structure", "abstract": "amino acid transformer",
                          "pub_year": 2020})
        else:
            metas.append({"title": "quantum surface code", "abstract": "qubits error correction",
                          "pub_year": 2021})
    return ids, vectors, metas


def test_layout_is_deterministic_and_stable(tmp_path):
    ids, vectors, metas = _blobs()
    first = GalaxyMap(tmp_path / "a").sync(ids, vectors, metas)
    second = GalaxyMap(tmp_path / "b").sync(ids, vectors, metas)
    assert [(p["id"], p["x"], p["y"], p["z"], p["cluster_id"]) for p in first] == \
           [(p["id"], p["x"], p["y"], p["z"], p["cluster_id"]) for p in second]
    assert len({p["x"] for p in first}) > 1
    assert len({p["cluster_id"] for p in first[:6]}) == 1
    assert len({p["cluster_id"] for p in first[6:]}) == 1
    assert first[0]["cluster_id"] != first[6]["cluster_id"]
    assert any(word in first[0]["cluster_label"] for word in ("protein", "folding", "amino", "structure"))
    assert "quantum" not in first[0]["cluster_label"]
    assert first[0]["year"] == 2020 and first[6]["year"] == 2021

    extra_id = ids + ["Pnew"]
    extra_vec = np.vstack([vectors, vectors[:1]])
    extra_meta = metas + [dict(metas[0], pub_year=2022)]
    grown = GalaxyMap(tmp_path / "a").sync(extra_id, extra_vec, extra_meta)
    by_id = {p["id"]: p for p in grown}
    for old in first:
        now = by_id[old["id"]]
        assert (now["x"], now["y"], now["z"], now["cluster_id"]) == \
               (old["x"], old["y"], old["z"], old["cluster_id"])
    assert by_id["Pnew"]["cluster_id"] == first[0]["cluster_id"]
    assert by_id["Pnew"]["year"] == 2022

    refit = GalaxyMap(tmp_path / "a").sync(extra_id, extra_vec, extra_meta, refit=True)
    fresh = GalaxyMap(tmp_path / "c").sync(extra_id, extra_vec, extra_meta)
    assert [(p["x"], p["y"], p["z"], p["cluster_id"]) for p in refit] == \
           [(p["x"], p["y"], p["z"], p["cluster_id"]) for p in fresh]


def test_new_paper_below_centroid_threshold_is_unclustered(tmp_path):
    vectors = np.zeros((5, 8), dtype=np.float32)
    vectors[:, 0] = 1
    ids = [f"A{i}" for i in range(5)]
    metas = [{"title": "protein folding", "abstract": "structure", "pub_year": 2019} for _ in ids]
    galaxy = GalaxyMap(tmp_path / "g", min_sim=0.99)
    galaxy.sync(ids, vectors, metas)
    ortho = np.zeros((1, 8), dtype=np.float32)
    ortho[0, 1] = 1
    points = galaxy.sync(ids + ["B"], np.vstack([vectors, ortho]),
                         metas + [{"title": "zzzz", "abstract": "yyyy", "pub_year": 2024}])
    newbie = next(p for p in points if p["id"] == "B")
    assert newbie["cluster_id"] == -1 and newbie["cluster_label"] == "unclustered"
    assert newbie["year"] == 2024


def test_cli_index_writes_a_galaxy(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ML_EMBEDDER", "hash")
    monkeypatch.setenv("ML_VECTOR_BACKEND", "local")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("ML_DATA_DIR", str(tmp_path / "ml"))
    papers = tmp_path / "works.jsonl"
    papers.write_text('{"id": "W1", "title": "Protein folding", "abstract": "transformers predict structure", "year": 2020}\n',
                      encoding="utf-8")
    from ml.cli import main
    main(["index", "--jsonl", str(papers)])
    assert not (tmp_path / "ml" / "galaxy" / "state.json").exists()   # galaxy is opt-in now
    main(["index", "--jsonl", str(papers), "--galaxy"])
    assert (tmp_path / "ml" / "galaxy" / "state.json").exists()
    out = capsys.readouterr().out
    assert "indexed 1 papers" in out and "skipped 1 existing" in out
    main(["galaxy"])
    assert "galaxy 1 nodes" in capsys.readouterr().out
    main(["update", "--jsonl", str(papers)])
    assert "galaxy 1 nodes" in capsys.readouterr().out
    stored = LocalStore(tmp_path / "ml" / "vectors").get_document("galaxy")
    assert stored["nodes"] and stored["nodes"][0]["id"] == "W1"


def test_reembed_refits_and_update_honors_refit(tmp_path, monkeypatch):
    monkeypatch.setenv("ML_EMBEDDER", "hash")
    monkeypatch.setenv("ML_VECTOR_BACKEND", "local")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("ML_DATA_DIR", str(tmp_path / "ml"))
    papers = tmp_path / "works.jsonl"
    papers.write_text(
        '{"id": "W1", "title": "Protein folding", "abstract": "transformers predict structure", "year": 2020}\n',
        encoding="utf-8")
    calls = []

    def fake_rebuild(self, refit=False):
        calls.append(bool(refit))
        return {"nodes": [{"id": "W1"}], "clusters": [], "links": []}

    monkeypatch.setattr("ml.service.MLService.rebuild_galaxy", fake_rebuild)
    from ml.cli import main
    main(["index", "--jsonl", str(papers)])
    assert calls == []
    main(["index", "--jsonl", str(papers), "--galaxy"])
    main(["index", "--jsonl", str(papers), "--reembed", "--galaxy"])
    main(["galaxy"])
    main(["galaxy", "--refit"])
    main(["update", "--jsonl", str(papers)])
    main(["update", "--jsonl", str(papers), "--refit"])
    assert calls == [False, True, False, True, False, True]


def test_service_galaxy_round_trip(tmp_path):
    papers = [
        Paper("W1", "Transformers for protein structure", "Attention predicts protein folding contacts.", 2021,
              topics=["Protein folding"], cited_by=4),
        Paper("W2", "Surface codes correct quantum errors", "Stabilizers protect logical qubits from noise.", 2020,
              topics=["Quantum codes"], cited_by=0),
    ]
    store = LocalStore(tmp_path / "v")
    svc = MLService(embedder=HashEmbedder(), store=store,
                    cache=SummaryCache(":memory:"), galaxy_dir=tmp_path / "g")
    assert svc.read_galaxy() == empty_graph()
    svc.index_papers(papers)
    assert svc.read_galaxy() == empty_graph()
    calls = {"rows": 0}
    real_rows = store.rows

    def counting_rows():
        calls["rows"] += 1
        return real_rows()

    store.rows = counting_rows
    graph = svc.rebuild_galaxy()
    assert calls["rows"] == 1
    assert {n["id"] for n in graph["nodes"]} == {"W1", "W2"}
    by_id = {n["id"]: n for n in graph["nodes"]}
    assert by_id["W1"]["year"] == 2021 and by_id["W2"]["year"] == 2020
    assert by_id["W1"]["topic_id"] == "protein-folding"
    assert by_id["W1"]["title"] == "Transformers for protein structure"
    assert by_id["W1"]["topic_name"] == "Protein folding"
    assert by_id["W2"]["topic_name"] == "Quantum codes"
    assert by_id["W1"]["support"] == 1.0
    assert isinstance(by_id["W1"]["cluster_id"], str)
    assert {c["id"] for c in graph["clusters"]} >= {n["cluster_id"] for n in graph["nodes"]}
    for cluster in graph["clusters"]:
        assert set(cluster) == {"id", "name", "label", "centroid", "size"}
        assert cluster["name"] == cluster["label"]
        assert set(cluster["centroid"]) == {"x", "y", "z"}
    ids = {n["id"] for n in graph["nodes"]}
    for link in graph["links"]:
        assert link["source"] in ids and link["target"] in ids
    assert svc.read_galaxy() == graph
    assert calls["rows"] == 1
    again = MLService(embedder=HashEmbedder(), store=LocalStore(tmp_path / "v"),
                      cache=SummaryCache(":memory:"), galaxy_dir=tmp_path / "g").read_galaxy()
    assert again == graph


def test_graph_links_are_capped_nearest_neighbours():
    points = []
    metas = []
    vectors = []
    for i in range(6):
        vec = np.zeros(4, dtype=np.float64)
        vec[0] = 1.0
        vec[1] = i / 10
        vectors.append(vec)
        points.append({"id": f"W{i}", "x": float(i), "y": 0.0, "z": 0.0,
                       "cluster_id": 0, "cluster_label": "shared, topic", "year": 2020})
        metas.append({"title": "Same title", "topics": ["Shared topic"], "cited_by": i or 0, "pub_year": 2020})
    graph = graph_from_layout(points, np.stack(vectors), metas, neighbours=2, max_edges=3)
    assert len(graph["links"]) == 3
    assert graph["links"] == sorted(graph["links"], key=lambda link: -link["weight"])
    assert {n["topic_name"] for n in graph["nodes"]} == {"Shared topic"}
    assert {n["title"] for n in graph["nodes"]} == {"Same title"}
    ids = {n["id"] for n in graph["nodes"]}
    assert ids == {f"W{i}" for i in range(6)}
    for link in graph["links"]:
        assert link["source"] in ids and link["target"] in ids
        assert link["source"] != link["target"]
    assert graph["clusters"][0]["size"] == 6
    assert graph["clusters"][0]["id"] == "0"
    assert knn_links(["a"], np.ones((1, 2))) == []
    assert graph_from_layout([], np.zeros((0, 2)), []) == empty_graph()
