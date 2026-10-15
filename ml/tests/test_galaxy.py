import numpy as np

from ml.embeddings import HashEmbedder
from ml.galaxy import GalaxyMap, cluster_ids, ctfidf_labels, resolve_method
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
    monkeypatch.setenv("ML_DATA_DIR", str(tmp_path / "ml"))
    papers = tmp_path / "works.jsonl"
    papers.write_text('{"id": "W1", "title": "Protein folding", "abstract": "transformers predict structure", "year": 2020}\n',
                      encoding="utf-8")
    from ml.cli import main
    main(["index", "--jsonl", str(papers)])
    assert (tmp_path / "ml" / "galaxy" / "state.json").exists()
    assert "indexed 1 papers" in capsys.readouterr().out
    main(["galaxy"])
    assert "galaxy 1 points" in capsys.readouterr().out


def test_service_galaxy_round_trip(tmp_path):
    papers = [
        Paper("W1", "Transformers for protein structure", "Attention predicts protein folding contacts.", 2021),
        Paper("W2", "Surface codes correct quantum errors", "Stabilizers protect logical qubits from noise.", 2020),
    ]
    svc = MLService(embedder=HashEmbedder(), store=LocalStore(tmp_path / "v"),
                    cache=SummaryCache(":memory:"), galaxy_dir=tmp_path / "g")
    assert svc.galaxy() == []
    svc.index_papers(papers)
    points = svc.galaxy()
    assert {p["id"] for p in points} == {"W1", "W2"}
    assert svc.galaxy() == points
    again = MLService(embedder=HashEmbedder(), store=LocalStore(tmp_path / "v"),
                      cache=SummaryCache(":memory:"), galaxy_dir=tmp_path / "g").galaxy()
    assert again == points
