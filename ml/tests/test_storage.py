import numpy as np
import pytest

from ml.store import (DOCUMENT_KINDS, LocalStore, PgVectorStore, check_kind, get_store,
                      migration_sql, split_sql)


def test_document_kinds_cover_shared_snapshots():
    assert {"galaxy", "galaxy_state", "patterns", "countries", "topics",
            "topic_country_year"} <= set(DOCUMENT_KINDS)


def test_local_documents_round_trip(tmp_path):
    store = LocalStore(tmp_path)
    store.put_document("countries", {"PK": 3})
    store.put_document("topics", {"protein": 2})
    assert store.get_document("missing") is None
    again = LocalStore(tmp_path)
    assert again.get_document("countries") == {"PK": 3}
    assert again.get_document("topics") == {"protein": 2}
    assert (tmp_path / "documents" / "countries.json").exists()


def test_document_kind_is_a_safe_name():
    with pytest.raises(ValueError):
        check_kind("../secrets")
    with pytest.raises(ValueError):
        check_kind("Countries")
    assert check_kind("topic_country_year") == "topic_country_year"


def test_migration_statements_cover_embeddings_and_documents():
    sql = "\n".join(migration_sql())
    assert "CREATE EXTENSION IF NOT EXISTS vector" in sql
    assert "CREATE TABLE IF NOT EXISTS documents" in sql
    assert "paper_embeddings_hnsw" in sql
    assert "ADD COLUMN IF NOT EXISTS meta" in sql
    joined = split_sql(sql)
    assert any(stmt.strip().startswith("DO $$") for stmt in joined)
    assert all(stmt.rstrip().endswith(";") for stmt in joined)


def test_pg_documents_use_the_documents_table():
    class Cur:
        def __init__(self, log, payload):
            self.log = log
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, sql, params=None):
            self.log.append((sql, params))

        def fetchone(self):
            return (self.payload,)

        def fetchall(self):
            return []

    class Conn:
        def __init__(self):
            self.log = []

        def cursor(self):
            return Cur(self.log, {"nodes": []})

    conn = Conn()
    store = PgVectorStore(conn=conn)
    store.put_document("patterns", {"items": ["a"]})
    assert store.get_document("patterns") == {"nodes": []}
    text = "\n".join(sql for sql, _ in conn.log)
    assert "CREATE EXTENSION IF NOT EXISTS vector" in text
    assert "INSERT INTO documents" in text
    assert "SELECT payload FROM documents" in text
    with pytest.raises(ValueError):
        store.put_document("bad kind", {})


def test_get_store_follows_database_url(tmp_path, monkeypatch):
    monkeypatch.setenv("ML_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("ML_VECTOR_BACKEND", raising=False)
    assert isinstance(get_store(), LocalStore)

    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/db")
    monkeypatch.setattr("ml.store.PgVectorStore", lambda dsn=None, conn=None: ("pg", dsn))
    assert get_store() == ("pg", None)

    monkeypatch.setenv("ML_VECTOR_BACKEND", "local")
    assert isinstance(get_store(), LocalStore)

    monkeypatch.setenv("ML_VECTOR_BACKEND", "pgvector")
    assert get_store() == ("pg", None)


def test_pg_rows_still_parse_meta():
    class Cur:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, sql, params=None):
            return None

        def fetchall(self):
            return [("W1", "[0.0, 1.0]", {"title": "t"})]

        def fetchone(self):
            return None

    class Conn:
        def cursor(self):
            return Cur()

    ids, vecs, metas = PgVectorStore(conn=Conn()).rows()
    assert ids == ["W1"] and vecs.shape == (1, 2) and metas[0]["title"] == "t"
    assert not np.isnan(vecs).any()
