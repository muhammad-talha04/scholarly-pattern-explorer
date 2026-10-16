"""FastEmbedder, per-model search floor and model labels. Offline: fastembed is faked."""
import sys
import types

import numpy as np
import pytest

from ml import embeddings as E
from ml.embeddings import Embedder, FastEmbedder, HashEmbedder, min_search_score, model_label
from ml.indexer import ModelMismatch, index
from ml.papers import Paper
from ml.service import MLService, SummaryCache
from ml.store import LocalStore

BGE = "BAAI/bge-small-en-v1.5"
MINILM = "sentence-transformers/all-MiniLM-L6-v2"


class FakeTextEmbedding:
    instances = []

    def __init__(self, model_name, cache_dir=None, **kw):
        self.model_name, self.cache_dir, self.calls = model_name, cache_dir, []
        FakeTextEmbedding.instances.append(self)

    def embed(self, texts, batch_size=256, **kw):
        texts = list(texts)
        self.calls.append({"texts": texts, "batch_size": batch_size})
        for t in texts:   # deterministic, un-normalised, 384-d
            v = np.zeros(384, dtype=np.float32)
            v[len(t) % 384] = 3.0
            v[0] += 4.0
            yield v


@pytest.fixture(autouse=True)
def fake_fastembed(monkeypatch):
    FakeTextEmbedding.instances = []
    monkeypatch.setitem(sys.modules, "fastembed", types.SimpleNamespace(TextEmbedding=FakeTextEmbedding))
    for k in ("ML_EMBED_BATCH_SIZE", "FASTEMBED_CACHE_PATH", "ML_EMBED_MODEL_REVISION",
              "SEARCH_MIN_SCORE", "ML_SEARCH_MIN_SCORE", "ML_EMBED_MODEL"):
        monkeypatch.delenv(k, raising=False)


def test_encode_normalises_prefixes_and_passes_batch_size():
    e = FastEmbedder(BGE)
    q = e.encode_queries(["solar"])
    d = e.encode_documents(["solar", "wind"])
    assert q.shape == (1, 384) and d.shape == (2, 384)
    assert np.allclose(np.linalg.norm(d, axis=1), 1.0)
    m = FakeTextEmbedding.instances[0]
    assert m.model_name == BGE
    assert m.calls[0]["texts"][0].startswith("Represent this sentence") and m.calls[0]["texts"][0].endswith("solar")
    assert m.calls[1]["texts"] == ["solar", "wind"]          # bge passages have no prefix
    assert all(c["batch_size"] == 32 for c in m.calls)       # not fastembed's default 256


def test_batch_size_configurable(monkeypatch):
    FastEmbedder(MINILM, batch_size=8).encode(["a"])
    monkeypatch.setenv("ML_EMBED_BATCH_SIZE", "16")
    FastEmbedder(MINILM).encode(["a"])
    assert [i.calls[0]["batch_size"] for i in FakeTextEmbedding.instances] == [8, 16]
    with pytest.raises(ValueError):
        FastEmbedder(MINILM, batch_size=0)


def test_empty_input_does_not_load_model():
    assert FastEmbedder(BGE).encode([]).shape == (0, 384)
    assert FakeTextEmbedding.instances == []


def test_cache_dir_inside_project_or_env(monkeypatch, tmp_path):
    FastEmbedder(BGE).encode(["x"])
    from ml.paths import REPO_ROOT
    assert FakeTextEmbedding.instances[-1].cache_dir == str(REPO_ROOT / ".cache" / "fastembed")
    monkeypatch.setenv("FASTEMBED_CACHE_PATH", str(tmp_path))
    FastEmbedder(BGE).encode(["x"])
    assert FakeTextEmbedding.instances[-1].cache_dir == str(tmp_path)


def test_get_embedder_picks_backend(monkeypatch):
    monkeypatch.setenv("ML_EMBEDDER", "fastembed")
    monkeypatch.setenv("ML_EMBED_MODEL", BGE)
    e = E.get_embedder()
    assert isinstance(e, FastEmbedder) and e.model_name == BGE
    monkeypatch.setenv("ML_EMBEDDER", "hash")
    assert isinstance(E.get_embedder(), HashEmbedder)


def test_labels_keep_fastembed_and_torch_apart(monkeypatch):
    monkeypatch.setattr(E, "fastembed_version", lambda: "0.9.0")
    assert model_label(HashEmbedder()) == "hash-v1"
    assert model_label(Embedder(BGE)) == f"{BGE}@main"
    assert model_label(FastEmbedder(BGE)) == f"fastembed:{BGE}@fastembed-0.9.0"
    assert model_label(FastEmbedder(BGE)) != model_label(Embedder(BGE))
    monkeypatch.setenv("ML_EMBED_MODEL_REVISION", "r1")
    assert model_label(FastEmbedder(BGE)) == f"fastembed:{BGE}@r1"
    assert model_label(Embedder(BGE)) == f"{BGE}@r1"


def test_indexer_refuses_to_mix_fastembed_into_torch_table(monkeypatch):
    monkeypatch.delenv("ML_EMBEDDER", raising=False)
    store = LocalStore()
    papers = [Paper(work_id=f"W{i}", title=f"paper {i}", abstract="x") for i in range(3)]

    class TorchBge(HashEmbedder):          # offline stand-in for sentence-transformers bge
        def __init__(self):
            super().__init__()
            self.model_name = BGE
    index(store, papers, embedder=TorchBge())
    with pytest.raises(ModelMismatch, match="fastembed:"):
        index(store, papers, embedder=FastEmbedder(BGE))
    r = index(store, papers, embedder=FastEmbedder(BGE), reembed=True)
    assert r.embedded == 3 and set(store.models.values()) == {model_label(FastEmbedder(BGE))}


@pytest.mark.parametrize("model,floor", [
    (HashEmbedder(), 0.0), ("hash", 0.0),
    (MINILM, 0.38), ("all-MiniLM-L6-v2", 0.38),
    (BGE, 0.68), ("bge-small-en-v1.5", 0.68),
    ("intfloat/e5-small-v2", 0.0),          # uncalibrated: off
])
def test_floor_per_model(model, floor):
    assert min_search_score(model) == floor


def test_floor_from_embedder_objects():
    assert min_search_score(FastEmbedder(BGE)) == 0.68
    assert min_search_score(FastEmbedder(MINILM)) == 0.38


def test_floor_env_override(monkeypatch):
    monkeypatch.setenv("ML_SEARCH_MIN_SCORE", "0.5")
    assert min_search_score(BGE) == 0.5
    monkeypatch.setenv("SEARCH_MIN_SCORE", "0")       # SEARCH_MIN_SCORE wins; 0 = off
    assert min_search_score(BGE) == 0.0


def test_search_applies_floor(tmp_path, monkeypatch):
    class Scored(HashEmbedder):
        def __init__(self, name):
            super().__init__()
            self.model_name = name
    papers = [Paper("W1", "Quantum error correction with surface codes", "Surface codes protect qubits."),
              Paper("W2", "Crop yield forecasting", "Satellite images predict wheat yield.")]
    for name, expect_empty in (("hash", False), (BGE, True)):
        svc = MLService(embedder=Scored(name), store=LocalStore(tmp_path / name.replace("/", "_")),
                        cache=SummaryCache(":memory:"))
        svc.index_papers(papers)
        hits = svc.search("medieval french poetry", k=5)
        assert (hits == []) is expect_empty, name
        if name == BGE:
            monkeypatch.setenv("SEARCH_MIN_SCORE", "0")
            assert svc.search("medieval french poetry", k=5)
            monkeypatch.delenv("SEARCH_MIN_SCORE")


def test_prefetch_main(monkeypatch, tmp_path):
    from ml import prefetch_model
    monkeypatch.setenv("FASTEMBED_CACHE_PATH", str(tmp_path))
    monkeypatch.setenv("ML_EMBEDDER", "hash")
    assert prefetch_model.main([]) == 0
    assert FakeTextEmbedding.instances[-1].model_name == BGE
    assert FakeTextEmbedding.instances[-1].cache_dir == str(tmp_path)

    def boom(*a, **k):
        raise OSError("no network")
    monkeypatch.setattr(prefetch_model, "prefetch", boom)
    assert prefetch_model.main([]) == 0                # hash deploy is not broken
    monkeypatch.setenv("ML_EMBEDDER", "fastembed")
    assert prefetch_model.main([]) == 1                # fastembed deploy must have its model


def test_export_corpus_round_trips_meta(tmp_path):
    from ml.export_corpus import export
    from ml.papers import read_works
    store = LocalStore(tmp_path / "vec")
    papers = [Paper("W2", "Quantum error correction", "Surface codes.", 2025, "https://doi.org/10.1/x",
                    ["QEC"], "2025-03-01", ["A. Author"], ["PK", "US"], 7, "https://example.org/w2.pdf"),
              Paper("W1", "No abstract", "", 2024)]
    store.upsert([p.work_id for p in papers], HashEmbedder().encode([p.text for p in papers]),
                 [p.to_dict() for p in papers], model="hash-v1")
    assert export(store, tmp_path / "out.jsonl") == 2
    back = {p.work_id: p.to_dict() for p in read_works(tmp_path / "out.jsonl")}
    assert back == {p.work_id: p.to_dict() for p in papers}
