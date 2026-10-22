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
    s.delete_all_embeddings()
