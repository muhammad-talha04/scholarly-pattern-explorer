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


def test_real_embedder_uses_minilm_mocked(monkeypatch):
    class Fake:
        def encode(self, texts, **kw):
            return np.ones((len(texts), 384))
    e = Embedder()
    assert "all-MiniLM-L6-v2" in e.model_name
    e._model = Fake()
    assert e.encode(["a", "b"]).shape == (2, 384)


def test_local_store_persist_and_upsert(tmp_path):
    s = LocalStore(tmp_path)
    v = np.eye(3, 384, dtype=np.float32)
    s.upsert(["a", "b", "c"], v, [{"t": 1}, {"t": 2}, {"t": 3}])
    s.upsert(["a"], v[:1], [{"t": 9}])
    s2 = LocalStore(tmp_path)
    assert len(s2) == 3 and s2.get("a") == {"t": 9}
    assert s2.search(v[1], 1)[0][0] == "b"


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


def test_pgvector_store_sql_with_fake_conn():
    class Cur:
        def __init__(s, log): s.log = log
        def __enter__(s): return s
        def __exit__(s, *a): pass
        def execute(s, sql, params=None): s.log.append((sql, params))
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
