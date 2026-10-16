import numpy as np

from ml import service as svc_mod
from ml.embeddings import Embedder
from ml.papers import Paper, abstract_from_inverted_index
from ml.store import LocalStore, PgVectorStore


def test_inverted_index_and_links():
    assert abstract_from_inverted_index({"world": [1], "hello": [0]}) == "hello world"
    p = Paper.from_openalex({"id": "https://openalex.org/W9", "title": "T", "doi": "https://doi.org/10.1/x",
                             "publication_year": 2020, "topics": [{"display_name": "A"}],
                             "abstract_inverted_index": {"hi": [0]}})
    assert p.work_id == "W9" and p.abstract == "hi" and p.topics == ["A"]
    assert p.openalex_url == "https://openalex.org/W9" and p.doi_url == "https://doi.org/10.1/x"
    from ml.papers import is_placeholder_doi, reader_url
    assert is_placeholder_doi("https://doi.org/10.1234/spe.0")
    assert reader_url("https://doi.org/10.1/a", "https://example.org/w1.pdf", p.openalex_url) == "https://doi.org/10.1/a"
    assert reader_url(None, "https://example.org/w1.pdf", p.openalex_url) == "https://example.org/w1.pdf"
    assert reader_url("10.1234/spe.0", "https://doi.org/10.1234/spe.0", p.openalex_url) == p.openalex_url
    assert reader_url(None, None, None) is None


def test_real_embedder_uses_minilm_mocked(monkeypatch):
    class Fake:
        def __init__(self):
            self.seen = []
        def encode(self, texts, **kw):
            self.seen.append(list(texts))
            return np.ones((len(texts), 384))
    e = Embedder()
    assert "all-MiniLM-L6-v2" in e.model_name
    e._model = Fake()
    assert e.encode(["a", "b"]).shape == (2, 384)
    assert e._model.seen == [["a", "b"]]
    e5 = Embedder("intfloat/e5-small-v2")
    e5._model = Fake()
    e5.encode_queries(["hello"])
    e5.encode_documents(["hello"])
    assert e5._model.seen[-2:] == [["query: hello"], ["passage: hello"]]


def test_local_store_persist_and_upsert(tmp_path):
    s = LocalStore(tmp_path)
    v = np.eye(3, 384, dtype=np.float32)
    s.upsert(["a", "b", "c"], v, [{"t": 1}, {"t": 2}, {"t": 3}])
    s.upsert(["a"], v[:1], [{"t": 9}])
    s2 = LocalStore(tmp_path)
    assert len(s2) == 3 and s2.get("a") == {"t": 9}
    assert s2.search(v[1], 1)[0][0] == "b"


def test_similar_orders_by_cosine(tmp_path):
    store = LocalStore(tmp_path / "v", dim=4)
    a = np.array([1, 0, 0, 0], dtype=np.float32)
    b = np.array([0.9, 0.1, 0, 0], dtype=np.float32)
    b /= np.linalg.norm(b)
    c = np.array([0, 0, 1, 0], dtype=np.float32)

    def meta(wid, title):
        return {"work_id": wid, "title": title, "pub_year": 2024, "topics": [title],
                "authors": [], "countries": [], "cited_by": 0, "abstract": "",
                "doi": None, "original_url": None}

    store.upsert(["A", "B", "C"], np.stack([a, b, c]),
                 [meta("A", "Alpha"), meta("B", "Beta"), meta("C", "Gamma")])
    from ml.embeddings import HashEmbedder
    from ml.service import MLService, SummaryCache
    svc = MLService(embedder=HashEmbedder(), store=store, cache=SummaryCache(":memory:"))
    hits = svc.similar("A", k=2)
    assert [h["work_id"] for h in hits] == ["B", "C"]
    assert hits[0]["score"] > hits[1]["score"] >= 0
    assert hits[0]["score"] > 0
    assert all(h["work_id"] != "A" for h in hits)
    assert svc.similar("missing") is None


def test_search_ranks_relevant_paper_first(service):
    res = service.search("surface codes qubits noise", k=2)
    assert res[0]["work_id"] == "W2"
    assert res[0]["openalex_url"] == "https://openalex.org/W2"
    assert 0 < res[0]["score"] <= 1.0001
    res = service.search("wheat yield satellite", k=1)
    assert res[0]["doi_url"] == "https://doi.org/10.2000/xyz"


def test_summary_cached_once(service, monkeypatch):
    first = service.summarize("W1")
    assert first["cached"] is False and first["method"] == "extractive" and first["summary"]
    monkeypatch.setattr(svc_mod, "extractive_summary", lambda *a, **k: 1 / 0)
    second = service.summarize("W1")
    assert second["cached"] is True and second["summary"] == first["summary"]
    assert service.summarize("nope") is None


def test_summary_uses_llm_when_configured(service, monkeypatch):
    monkeypatch.setattr(svc_mod, "chat_complete", lambda *a, **k: "LLM summary.")
    out = service.summarize("W2")
    assert out["method"] == "llm" and out["summary"] == "LLM summary."


def test_ask_grounded_fallback(service):
    out = service.ask("W3", "What crop is the yield predicted for?")
    assert out["method"] == "extractive"
    assert "wheat" in out["answer"].lower()
    out = service.ask("W3", "zzzz unrelated xyzzy")
    assert "does not seem" in out["answer"]


def test_ask_llm_failure_falls_back(service, monkeypatch):
    monkeypatch.setenv("ML_LLM_URL", "http://127.0.0.1:9")   # nothing listening
    out = service.ask("W2", "What thresholds were observed?")
    assert out["method"] == "extractive" and "percent" in out["answer"]


def test_pgvector_store_sql_with_fake_conn(monkeypatch):
    monkeypatch.setenv("SPE_RUN_MIGRATIONS", "1")  # migrations on connect are opt-in now
    class Cur:
        def __init__(s, log): s.log = log
        def __enter__(s): return s
        def __exit__(s, *a): pass
        def execute(s, sql, params=None): s.log.append((sql, params))
        def executemany(s, sql, rows): s.log.append((sql, rows))
        def fetchall(s): return [("W1", 0.9, {"title": "x"})]
        def fetchone(s): return ({"title": "x"},)
    class Conn:
        def __init__(s): s.log = []
        def cursor(s): return Cur(s.log)
    c = Conn()
    st = PgVectorStore(conn=c)
    st.upsert(["W1"], np.zeros((1, 384)), [{"title": "x"}])
    assert st.search(np.zeros(384), 5) == [("W1", 0.9, {"title": "x"})]
    assert any("CREATE EXTENSION IF NOT EXISTS vector" in q for q, _ in c.log)
    assert any("<=>" in q for q, _ in c.log)


def test_pgvector_rows_parse_embeddings():
    class Cur:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def execute(self, sql, params=None): pass
        def fetchall(self): return [("W1", "[0.0, 1.0]", {"title": "t", "pub_year": 2020})]
        def fetchone(self): return None
    class Conn:
        def cursor(self): return Cur()
    ids, vecs, metas = PgVectorStore(conn=Conn()).rows()
    assert ids == ["W1"] and vecs.shape == (1, 2) and metas[0]["pub_year"] == 2020
