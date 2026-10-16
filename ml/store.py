"""Vector storage: pgvector (Supabase) or a local FAISS / numpy fallback.

All vectors are L2-normalised, so cosine similarity == inner product.

The same store holds JSON documents (the precomputed galaxy, pattern snapshots,
country and topic counts). Postgres is used when ``DATABASE_URL`` is set, unless
``ML_VECTOR_BACKEND=local``. Otherwise documents are JSON files next to the
vectors, so tests run with no database.
"""
from __future__ import annotations

import contextlib
import json
import logging
import os
import re
from pathlib import Path
from typing import Protocol

import numpy as np

from .paths import ml_data_dir

# Shared JSON slots. Any kind matching the name pattern can be stored the same way.
DOCUMENT_KINDS = (
    "galaxy",              # GET /api/v1/galaxy body
    "galaxy_state",        # frozen PCA basis and assignments
    "patterns",            # pattern snapshot
    "countries",           # country counts
    "topics",              # topic counts
    "topic_country_year",  # topic × country × year counts
)

_KIND = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "db" / "migrations"


def check_kind(kind: str) -> str:
    if not isinstance(kind, str) or not _KIND.fullmatch(kind):
        raise ValueError("document kind must match ^[a-z][a-z0-9_]{0,63}$")
    return kind


def split_sql(sql: str) -> list[str]:
    """Split a migration on semicolons, keeping dollar-quoted blocks intact."""
    parts: list[str] = []
    buf: list[str] = []
    dollar = False
    for line in sql.splitlines():
        if not dollar and line.strip().startswith("--"):
            continue
        if line.count("$$") % 2 == 1:
            dollar = not dollar
        buf.append(line)
        if not dollar and line.strip().endswith(";"):
            stmt = "\n".join(buf).strip()
            if stmt:
                parts.append(stmt)
            buf = []
    tail = "\n".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def migration_files() -> list[Path]:
    """Numbered SQL files under db/migrations, in apply order."""
    return sorted(p for p in _MIGRATIONS_DIR.glob("[0-9]*.sql") if p.is_file())


def migration_sql() -> list[str]:
    statements: list[str] = []
    for path in migration_files():
        statements.extend(split_sql(path.read_text(encoding="utf-8")))
    return statements


class VectorStore(Protocol):
    def upsert(self, ids: list[str], vectors: np.ndarray, meta: list[dict], model: str | None = None) -> None: ...
    def search(self, query: np.ndarray, k: int = 10) -> list[tuple[str, float, dict]]: ...
    def get(self, work_id: str) -> dict | None: ...
    def vector(self, work_id: str): ...
    def rows(self): ...
    def put_document(self, kind: str, payload: dict) -> None: ...
    def get_document(self, kind: str) -> dict | None: ...
    def __len__(self) -> int: ...


class LocalStore:
    """numpy matrix persisted to disk; uses FAISS for search if it is installed."""

    def __init__(self, path: str | Path | None = None, dim: int = 384):
        self.path = Path(path) if path else None
        self.dim = dim
        self.ids: list[str] = []
        self.meta: dict[str, dict] = {}
        self.vecs = np.zeros((0, dim), dtype=np.float32)
        self._docs: dict[str, dict] = {}
        self.models: dict[str, str | None] = {}
        if self.path and (self.path / "vectors.npy").exists():
            self.vecs = np.load(self.path / "vectors.npy")
            self.dim = int(self.vecs.shape[1])
            data = json.loads((self.path / "meta.json").read_text(encoding="utf-8"))
            self.ids, self.meta = data["ids"], data["meta"]
            self.models = data.get("models") or {}
        if self.path and (self.path / "documents").is_dir():
            for f in sorted((self.path / "documents").glob("*.json")):
                if _KIND.fullmatch(f.stem):
                    self._docs[f.stem] = json.loads(f.read_text(encoding="utf-8"))

    def __len__(self):
        return len(self.ids)

    def rows(self):
        return list(self.ids), self.vecs, [self.meta.get(i, {}) for i in self.ids]

    def existing_ids(self) -> set[str]:
        return set(self.ids)

    def model_counts(self) -> dict[str | None, int]:
        out: dict[str | None, int] = {}
        for wid in self.ids:
            m = self.models.get(wid)
            out[m] = out.get(m, 0) + 1
        return out

    def delete_all_embeddings(self) -> None:
        self.ids, self.meta, self.models = [], {}, {}
        self.vecs = np.zeros((0, self.dim), dtype=np.float32)
        self._save()

    def database_size(self) -> int | None:
        return None

    def upsert(self, ids, vectors, meta, model: str | None = None):
        for wid in ids:
            self.models[wid] = model
        vectors = np.asarray(vectors, dtype=np.float32)
        if vectors.ndim == 1:
            vectors = vectors.reshape(1, -1)
        if len(self.ids) == 0 and vectors.shape[1] != self.vecs.shape[1]:
            self.dim = int(vectors.shape[1])
            self.vecs = np.zeros((0, self.dim), dtype=np.float32)
        index = {w: i for i, w in enumerate(self.ids)}
        new_rows = []
        for wid, v, m in zip(ids, vectors, meta):
            if wid in index:
                self.vecs[index[wid]] = v
            else:
                index[wid] = len(self.ids) + len(new_rows)
                new_rows.append(v)
                self.ids.append(wid)
            self.meta[wid] = m
        if new_rows:
            self.vecs = np.vstack([self.vecs, np.stack(new_rows)])
        self._save()

    def _save(self):
        if not self.path:
            return
        self.path.mkdir(parents=True, exist_ok=True)
        np.save(self.path / "vectors.npy", self.vecs)
        (self.path / "meta.json").write_text(json.dumps({"ids": self.ids, "meta": self.meta,
                                                         "models": self.models}),
                                             encoding="utf-8")

    def search(self, query, k=10):
        if not self.ids:
            return []
        q = np.asarray(query, dtype=np.float32).reshape(1, -1)
        k = min(k, len(self.ids))
        try:
            import faiss  # optional
            idx = faiss.IndexFlatIP(self.vecs.shape[1])
            idx.add(self.vecs)
            scores, rows = idx.search(q, k)
            pairs = list(zip(rows[0].tolist(), scores[0].tolist()))
        except ImportError:
            sims = self.vecs @ q[0]
            rows = np.argsort(-sims)[:k]
            pairs = [(int(r), float(sims[r])) for r in rows]
        return [(self.ids[r], float(s), self.meta[self.ids[r]]) for r, s in pairs]

    def get(self, work_id):
        return self.meta.get(work_id)

    def vector(self, work_id):
        try:
            return self.vecs[self.ids.index(work_id)]
        except ValueError:
            return None

    def put_document(self, kind: str, payload: dict) -> None:
        kind = check_kind(kind)
        if not isinstance(payload, dict):
            raise TypeError("document payload must be a dict")
        blob = json.loads(json.dumps(payload))
        self._docs[kind] = blob
        if not self.path:
            return
        dest = self.path / "documents"
        dest.mkdir(parents=True, exist_ok=True)
        (dest / f"{kind}.json").write_text(json.dumps(blob), encoding="utf-8")

    def get_document(self, kind: str) -> dict | None:
        kind = check_kind(kind)
        payload = self._docs.get(kind)
        if payload is None:
            return None
        return json.loads(json.dumps(payload))


def _vec_literal(v) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in np.asarray(v).ravel()) + "]"


log = logging.getLogger(__name__)


def migrations_on_connect() -> bool:
    """Back-compat opt-in: SPE_RUN_MIGRATIONS=1 applies db/migrations when a store connects.

    Off by default. Run ``python -m db.apply`` once per deploy instead, so a cold
    start does not run DDL and a request never waits on it.
    """
    return os.getenv("SPE_RUN_MIGRATIONS", "").strip().lower() in ("1", "true", "yes")


def _operational_error():
    try:
        import psycopg
        return psycopg.OperationalError
    except ImportError:  # pragma: no cover
        return ConnectionError


class _Borrowed:
    """``store.conn.cursor()`` for callers that only need a cursor (research_gaps).

    Each ``with`` borrows a pooled connection and returns it afterwards.
    """

    def __init__(self, store):
        self._store = store

    def cursor(self):
        return self._store._cursor()


class PgVectorStore:
    """Supabase Postgres + pgvector. Needs psycopg (v3) and DATABASE_URL.

    Connections come from a small ``psycopg_pool.ConnectionPool``
    (``PG_POOL_MIN``/``PG_POOL_MAX``, default 1/4) that checks a connection before
    handing it out, so a connection the server dropped is replaced instead of
    failing the request. Without psycopg_pool, one connection is kept and a query
    that hits ``OperationalError`` reconnects and is retried once.

    Migrations are not applied here unless ``SPE_RUN_MIGRATIONS=1``; use
    ``python -m db.apply``.
    """

    def __init__(self, dsn: str | None = None, conn=None, pool=None):
        self._dsn = dsn or (None if (conn is not None or pool is not None) else os.environ["DATABASE_URL"])
        self._pool = pool
        self._single = conn
        if pool is None and conn is None:
            try:
                from psycopg_pool import ConnectionPool
                self._pool = ConnectionPool(
                    self._dsn, min_size=int(os.getenv("PG_POOL_MIN", "1")),
                    max_size=int(os.getenv("PG_POOL_MAX", "4")),
                    kwargs={"autocommit": True}, check=ConnectionPool.check_connection,
                    open=True, name="spe")
            except ImportError:
                self._single = self._connect()
        if migrations_on_connect():
            with self._cursor() as cur:
                for stmt in migration_sql():
                    cur.execute(stmt)

    # ---- connections ----
    def _connect(self):
        import psycopg
        return psycopg.connect(self._dsn, autocommit=True)

    @property
    def conn(self):
        return self._single if self._pool is None else _Borrowed(self)

    @contextlib.contextmanager
    def _connection(self):
        if self._pool is not None:
            with self._pool.connection() as c:
                yield c
        else:
            yield self._single

    @contextlib.contextmanager
    def _cursor(self):
        with self._connection() as c:
            with c.cursor() as cur:
                yield cur

    def _run(self, fn):
        """Run fn(cursor). On a dropped connection, reconnect and retry once."""
        err = _operational_error()
        try:
            with self._cursor() as cur:
                return fn(cur)
        except err:
            if self._pool is not None:
                self._pool.check()          # drop dead connections, then retry once
            elif self._dsn:
                log.warning("postgres connection lost; reconnecting once")
                try:
                    self._single.close()
                except Exception:
                    pass
                self._single = self._connect()
            else:
                raise
            with self._cursor() as cur:
                return fn(cur)

    def close(self):
        if self._pool is not None:
            self._pool.close()

    def __len__(self):
        def q(cur):
            cur.execute("SELECT count(*) FROM paper_embeddings")
            return cur.fetchone()[0]
        return self._run(q)

    # ---- writes ----
    _UPSERT = ("INSERT INTO paper_embeddings (work_id, embedding, meta, model) "
               "VALUES (%s, %s::vector, %s::jsonb, %s) ON CONFLICT (work_id) DO UPDATE "
               "SET embedding = EXCLUDED.embedding, meta = EXCLUDED.meta, model = EXCLUDED.model")

    def upsert(self, ids, vectors, meta, model: str | None = None):
        rows = [(wid, _vec_literal(v), json.dumps(m), model) for wid, v, m in zip(ids, vectors, meta)]
        if not rows:
            return
        with self._connection() as c:
            tx = c.transaction() if hasattr(c, "transaction") else contextlib.nullcontext()
            with tx, c.cursor() as cur:
                cur.executemany(self._UPSERT, rows)   # one transaction = one commit per batch

    def existing_ids(self) -> set[str]:
        def q(cur):
            cur.execute("SELECT work_id FROM paper_embeddings")
            return {r[0] for r in cur.fetchall()}
        return self._run(q)

    def model_counts(self) -> dict[str | None, int]:
        def q(cur):
            cur.execute("SELECT model, count(*) FROM paper_embeddings GROUP BY model")
            return {m: int(n) for m, n in cur.fetchall()}
        return self._run(q)

    def delete_all_embeddings(self) -> None:
        with self._cursor() as cur:
            cur.execute("DELETE FROM paper_embeddings")

    def database_size(self) -> int:
        def q(cur):
            cur.execute("SELECT pg_database_size(current_database())")
            return int(cur.fetchone()[0])
        return self._run(q)

    # ---- reads ----
    def search(self, query, k=10):
        lit = _vec_literal(query)

        def q(cur):
            cur.execute(
                "SELECT work_id, 1 - (embedding <=> %s::vector) AS score, meta "
                "FROM paper_embeddings ORDER BY embedding <=> %s::vector LIMIT %s",
                (lit, lit, k))
            return cur.fetchall()
        rows = self._run(q)
        return [(w, float(s), m if isinstance(m, dict) else json.loads(m)) for w, s, m in rows]

    def get(self, work_id):
        def q(cur):
            cur.execute("SELECT meta FROM paper_embeddings WHERE work_id = %s", (work_id,))
            return cur.fetchone()
        row = self._run(q)
        if not row:
            return None
        return row[0] if isinstance(row[0], dict) else json.loads(row[0])

    def vector(self, work_id):
        def q(cur):
            cur.execute("SELECT embedding::text FROM paper_embeddings WHERE work_id = %s", (work_id,))
            return cur.fetchone()
        row = self._run(q)
        return None if not row else np.array(json.loads(row[0]), dtype=np.float32)

    def rows(self):
        def q(cur):
            cur.execute("SELECT work_id, embedding::text, meta FROM paper_embeddings")
            return cur.fetchall()
        fetched = self._run(q)
        if not fetched:
            return [], np.zeros((0, 384), dtype=np.float32), []
        ids, vecs, metas = [], [], []
        for wid, emb, meta in fetched:
            ids.append(wid)
            vecs.append(np.array(json.loads(emb), dtype=np.float32))
            metas.append(meta if isinstance(meta, dict) else json.loads(meta))
        return ids, np.stack(vecs), metas

    def put_document(self, kind: str, payload: dict) -> None:
        kind = check_kind(kind)
        if not isinstance(payload, dict):
            raise TypeError("document payload must be a dict")
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO documents (kind, payload, updated_at) VALUES (%s, %s::jsonb, now()) "
                "ON CONFLICT (kind) DO UPDATE SET payload = EXCLUDED.payload, updated_at = now()",
                (kind, json.dumps(payload)))

    def get_document(self, kind: str) -> dict | None:
        kind = check_kind(kind)

        def q(cur):
            cur.execute("SELECT payload FROM documents WHERE kind = %s", (kind,))
            return cur.fetchone()
        row = self._run(q)
        if not row:
            return None
        return row[0] if isinstance(row[0], dict) else json.loads(row[0])


def get_store():
    """Postgres + pgvector when DATABASE_URL is set, unless ML_VECTOR_BACKEND=local.

    ``ML_VECTOR_BACKEND=pgvector`` forces Postgres and needs ``DATABASE_URL``.
    With neither set, embeddings and documents are files under ``ML_DATA_DIR``.
    """
    backend = os.getenv("ML_VECTOR_BACKEND", "").strip().lower()
    if backend == "local":
        return LocalStore(ml_data_dir() / "vectors")
    if backend == "pgvector" or os.getenv("DATABASE_URL"):
        return PgVectorStore()
    return LocalStore(ml_data_dir() / "vectors")
