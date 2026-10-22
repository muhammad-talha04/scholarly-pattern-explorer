"""Batched indexer, pooled PgVectorStore and search timings. All fakes, no database."""
import logging

import numpy as np
import pytest

from ml.embeddings import HashEmbedder, model_label
from ml.indexer import ModelMismatch, index, stored_models
from ml.papers import Paper
from ml.store import LocalStore, PgVectorStore
from ml import timing


class OpErr(Exception):
    """Stands in for psycopg.OperationalError (CI's ml job has no psycopg)."""


@pytest.fixture(autouse=True)
def _op_error(monkeypatch):
    monkeypatch.setattr("ml.store._operational_error", lambda: OpErr)


def _papers(n, start=0):
    return [Paper(work_id=f"W{i}", title=f"paper {i} graph networks", abstract="x")
            for i in range(start, start + n)]


class Named(HashEmbedder):
    """Stand-in for a sentence-transformers model, still offline."""
    def __init__(self, name):
        super().__init__()
        self.model_name = name


@pytest.fixture
def hash_mode(monkeypatch):
    monkeypatch.setenv("ML_EMBEDDER", "hash")


def test_model_label():
    assert model_label(HashEmbedder()) == "hash-v1"
    assert model_label(Named("BAAI/bge-small-en-v1.5")) == "BAAI/bge-small-en-v1.5@main"


def test_resume_embeds_only_new_ids_in_batches(hash_mode, caplog):
    store = LocalStore()
    caplog.set_level(logging.INFO, "spe.indexer")
    r1 = index(store, _papers(5), batch_size=2)
    assert (r1.embedded, r1.batches) == (5, 3) and len(store) == 5
    r2 = index(store, _papers(8), batch_size=2)
    assert r2.embedded == 3 and r2.skipped_existing == 5 and len(store) == 8
    assert set(store.models.values()) == {"hash-v1"}
    assert "batch 3: 5/5 embedded" in caplog.text


def test_refuses_other_model_unless_reembed(hash_mode):
    store = LocalStore()
    index(store, _papers(3), embedder=Named("all-MiniLM-L6-v2"))
    with pytest.raises(ModelMismatch, match="all-MiniLM-L6-v2@main"):
        index(store, _papers(4))
    r = index(store, _papers(4), reembed=True)
    assert r.deleted == 3 and r.embedded == 4
    assert stored_models(store) == {"hash-v1": 4}


def test_null_model_rows_are_hash_only_in_hash_mode(monkeypatch):
    store = LocalStore()
    store.upsert(["W0"], HashEmbedder().encode(["a"]), [{}])     # legacy row, model NULL
    monkeypatch.setenv("ML_EMBEDDER", "hash")
    assert index(store, _papers(2)).embedded == 1                 # W0 counted as hash-v1
    monkeypatch.delenv("ML_EMBEDDER")
    with pytest.raises(ModelMismatch, match="legacy"):
        index(store, _papers(2), embedder=Named("e5-small-v2"))


def test_size_limit_stops_before_batch(hash_mode):
    store = LocalStore()
    sizes = iter([100, 500])
    store.database_size = lambda: next(sizes)
    r = index(store, _papers(5), batch_size=2, max_db_bytes=400)
    assert r.stopped_for_size and r.embedded == 2 and "3 papers left" in r.notes[0]


# ---- PgVectorStore with fakes ----
class Cur:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        if self.conn.fail_next:
            self.conn.fail_next -= 1
            raise OpErr("server closed the connection")
        self.conn.log.append(sql)
        self.last = sql

    def executemany(self, sql, rows):
        self.conn.log.append(sql)
        self.conn.many.append(list(rows))

    def fetchone(self):
        return (7,)

    def fetchall(self):
        if "GROUP BY model" in self.last:
            return [(None, 2), ("hash-v1", 3)]
        return [("W1",), ("W2",)]


class Conn:
    def __init__(self, fail_next=0):
        self.log, self.many, self.fail_next, self.tx = [], [], fail_next, 0

    def cursor(self):
        return Cur(self)

    def transaction(self):
        conn = self

        class Tx:
            def __enter__(self):
                conn.tx += 1

            def __exit__(self, *a):
                return False
        return Tx()

    def close(self):
        pass


class Pool:
    def __init__(self, conn):
        self.c, self.checked = conn, 0

    def connection(self):
        import contextlib
        return contextlib.nullcontext(self.c)

    def check(self):
        self.checked += 1


def test_no_migrations_on_connect_by_default(monkeypatch):
    monkeypatch.delenv("SPE_RUN_MIGRATIONS", raising=False)
    c = Conn()
    PgVectorStore(conn=c)
    assert c.log == []
    monkeypatch.setenv("SPE_RUN_MIGRATIONS", "1")
    PgVectorStore(conn=c)
    assert any("CREATE EXTENSION" in s for s in c.log)


def test_pg_batch_upsert_writes_model_in_one_transaction(monkeypatch):
    monkeypatch.delenv("SPE_RUN_MIGRATIONS", raising=False)
    c = Conn()
    s = PgVectorStore(pool=Pool(c))
    s.upsert(["W1", "W2"], np.zeros((2, 3)), [{}, {}], model="hash-v1")
    assert c.tx == 1 and len(c.many[0]) == 2 and c.many[0][0][3] == "hash-v1"
    assert "model = EXCLUDED.model" in c.log[0]
    assert s.existing_ids() == {"W1", "W2"} and s.database_size() == 7
    assert s.model_counts() == {None: 2, "hash-v1": 3}
    with s.conn.cursor() as cur:       # research_gaps path still works through the pool
        cur.execute("SELECT 1")


def test_pool_retries_once_after_dropped_connection(monkeypatch):
    monkeypatch.delenv("SPE_RUN_MIGRATIONS", raising=False)
    c = Conn(fail_next=1)
    pool = Pool(c)
    assert len(PgVectorStore(pool=pool)) == 7 and pool.checked == 1
    c.fail_next = 2
    with pytest.raises(OpErr):
        len(PgVectorStore(pool=pool))   # only one retry


def test_single_connection_reconnects_once(monkeypatch):
    monkeypatch.delenv("SPE_RUN_MIGRATIONS", raising=False)
    bad, good = Conn(fail_next=1), Conn()
    s = PgVectorStore(conn=bad)
    s._dsn = "postgresql://example.invalid/db"
    monkeypatch.setattr(s, "_connect", lambda: good)
    assert len(s) == 7 and s._single is good


def test_search_stage_timings(hash_mode):
    from ml.service import MLService
    svc = MLService(store=LocalStore())
    index(svc.store, _papers(3))
    with timing.collect() as t:
        assert svc.search("graph", k=2)
    assert set(t) == {"embed", "vector"} and all(v >= 0 for v in t.values())
    assert timing.server_timing({"embed": 1.5, "vector": 2.0}) == "embed;dur=1.5, vector;dur=2.0"
