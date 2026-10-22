import os
import re

import numpy as np
import pytest

from ml.store import LocalStore, PgVectorStore, migration_files, split_sql


def test_migration_converts_to_halfvec_and_keeps_index_name():
    path = [p for p in migration_files() if p.name.startswith("005_")][0]
    sql = path.read_text()
    assert "halfvec(384)" in sql and "halfvec_cosine_ops" in sql
    assert "paper_embeddings_hnsw" in sql and "DROP INDEX IF EXISTS paper_embeddings_hnsw" in sql
    assert len(split_sql(sql)) == 2


def test_pg_queries_use_halfvec_casts():
    assert "%s::halfvec" in PgVectorStore._UPSERT
    import inspect
    src = inspect.getsource(PgVectorStore)
    assert "::vector)" not in src.replace("embedding::vector)", "")   # no float32 query casts left
    assert re.search(r"<=> %s::halfvec", src)


class _Cur:
    def __init__(self, log):
        self.log, self.connection = log, self

    def transaction(self):
        import contextlib
        self.log.append("BEGIN")
        return contextlib.nullcontext()

    def execute(self, sql, params=None):
        self.log.append(sql)

    def fetchall(self):
        return [("W1", 0.9, {"a": 1})]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Conn:
    def __init__(self):
        self.log = []

    def cursor(self):
        return _Cur(self.log)


def test_search_sets_ef_search_in_transaction(monkeypatch):
    monkeypatch.setenv("ML_HNSW_EF_SEARCH", "250")
    c = _Conn()
    s = PgVectorStore(conn=c)
    assert s.search(np.zeros(384), k=3)[0][0] == "W1"
    assert c.log[0] == "BEGIN" and c.log[1] == "SET LOCAL hnsw.ef_search = 250"
    assert "ORDER BY embedding <=>" in c.log[2]


def test_ef_search_default_and_bounds(monkeypatch):
    from ml.store import hnsw_ef_search
    monkeypatch.delenv("ML_HNSW_EF_SEARCH", raising=False)
    assert hnsw_ef_search() == 100
    monkeypatch.setenv("ML_HNSW_EF_SEARCH", "nope")
    assert hnsw_ef_search() == 100
    monkeypatch.setenv("ML_HNSW_EF_SEARCH", "99999")
    assert hnsw_ef_search() == 1000


def test_local_store_stored_dim(tmp_path):
    s = LocalStore(tmp_path)
    assert s.stored_dim() is None
    s.upsert(["W1"], np.ones((1, 384), dtype=np.float32) / np.sqrt(384), [{}], model="m")
    assert s.stored_dim() == 384


@pytest.mark.skipif(not os.getenv("SPE_TEST_PG_URL"), reason="needs a throwaway Postgres+pgvector")
def test_roundtrip_on_real_postgres():
    from db.apply import apply
    dsn = os.environ["SPE_TEST_PG_URL"]
    apply(dsn)
    apply(dsn)   # idempotent after the halfvec conversion
    s = PgVectorStore(dsn)
    s.delete_all_embeddings()
    rng = np.random.default_rng(0)
    v = rng.normal(size=(50, 384)).astype(np.float32)
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    s.upsert([f"W{i}" for i in range(50)], v, [{"i": i} for i in range(50)], model="m")
    assert s.stored_dim() == 384 and len(s) == 50
    hit = s.search(v[7], k=1)[0]
    assert hit[0] == "W7" and hit[1] > 0.999
    assert np.allclose(s.vector("W7"), v[7], atol=1e-3)
    # every vector finds itself through the HNSW index with ef_search applied
    assert all(s.search(v[i], k=1)[0][0] == f"W{i}" for i in range(50))
    with s._cursor() as cur:
        with cur.connection.transaction():
            cur.execute("SET LOCAL hnsw.ef_search = 100")
            cur.execute("SHOW hnsw.ef_search")
            assert cur.fetchone()[0] == "100"
        cur.execute("SHOW hnsw.ef_search")
        assert cur.fetchone()[0] == "40"   # SET LOCAL did not leak
    s.put_sampling_rate("2020-01", 1000, 5, "f")
    s.put_sampling_rate("2020-01", 1200, 6, "f")
    assert s.sampling_rates()["2020-01"]["openalex_total"] == 1200
    with s._cursor() as cur:
        cur.execute("DELETE FROM sampling_rates WHERE month = '2020-01-01'")
    s.delete_all_embeddings()
