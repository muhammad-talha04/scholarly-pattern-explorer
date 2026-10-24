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
    "galaxy_sample",       # small stratified galaxy for the hero view (GET /galaxy?limit=N)
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

    def stored_dim(self) -> int | None:
        """Dimension of the stored vectors, or None when nothing is stored."""
        return int(self.vecs.shape[1]) if len(self.ids) else None

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

    def month_counts(self) -> dict[str, int]:
        """Stored papers per month: meta.publication_date, else meta.created."""
        out: dict[str, int] = {}
        for wid in self.ids:
            m = _month_of(self.meta.get(wid))
            if m:
                out[m] = out.get(m, 0) + 1
        return out

    def aggregate_counts(self) -> dict:
        """Papers per (year, month) and fractional topic counts per (year, month, topic)."""
        return aggregate_meta(self.meta.get(i) for i in self.ids)

    def ids_missing_publication_date(self) -> list[str]:
        """work_ids whose meta has no ``publication_date`` key (null = looked up, unknown)."""
        return [w for w in self.ids if "publication_date" not in (self.meta.get(w) or {})]

    def set_publication_dates(self, dates: dict[str, str | None]) -> int:
        """Metadata-only update: sets meta.publication_date. Vectors and model untouched."""
        n = 0
        for wid, d in dates.items():
            if wid in self.meta:
                self.meta[wid] = {**(self.meta[wid] or {}), "publication_date": d}
                n += 1
        if n:
            self._save()
        return n

    def put_sampling_rate(self, month: str, openalex_total: int, sampled: int, filter: str) -> None:
        """File fallback for the sampling_rates table: <path>/sampling_rates.json."""
        if not self.path:
            self._rates = getattr(self, "_rates", {})
            rates = self._rates
        else:
            f = self.path / "sampling_rates.json"
            rates = json.loads(f.read_text()) if f.exists() else {}
        from datetime import datetime, timezone
        rates[month] = {"openalex_total": int(openalex_total), "sampled": int(sampled),
                        "filter": filter, "fetched_at": datetime.now(timezone.utc).isoformat()}
        if self.path:
            self.path.mkdir(parents=True, exist_ok=True)
            (self.path / "sampling_rates.json").write_text(json.dumps(rates, indent=1, sort_keys=True))

    def sampling_rates(self) -> dict[str, dict]:
        if not self.path:
            return dict(getattr(self, "_rates", {}))
        f = self.path / "sampling_rates.json"
        return json.loads(f.read_text()) if f.exists() else {}

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


def hnsw_ef_search() -> int:
    """HNSW candidate list size for search (ML_HNSW_EF_SEARCH, default 100, 1..1000).

    pgvector's default of 40 missed exact self-matches in testing; 100 keeps
    recall high at 70k rows for a few ms more per query.
    """
    try:
        ef = int(os.getenv("ML_HNSW_EF_SEARCH", "100"))
    except ValueError:
        ef = 100
    return max(1, min(ef, 1000))


def _month_of(meta: dict) -> str | None:
    meta = meta or {}
    d = meta.get("publication_date") or meta.get("created")
    return d[:7] if isinstance(d, str) and re.match(r"^\d{4}-\d{2}", d) else None


def _year_month(meta: dict) -> tuple[int | None, str | None]:
    """(year, 'YYYY-MM') for the aggregates. publication_date, else pub_year (year only), else created."""
    meta = meta or {}
    d = meta.get("publication_date")
    if isinstance(d, str) and re.match(r"^\d{4}-\d{2}", d):
        return int(d[:4]), d[:7]
    y = meta.get("pub_year")
    if isinstance(y, int) or (isinstance(y, str) and re.fullmatch(r"\d{4}", y)):
        return int(y), None
    c = meta.get("created")
    if isinstance(c, str) and re.match(r"^\d{4}-\d{2}", c):
        return int(c[:4]), c[:7]
    return None, None


def aggregate_meta(metas) -> dict:
    """Python twin of PgVectorStore.aggregate_counts() (LocalStore and tests)."""
    papers: dict[tuple, int] = {}
    topics: dict[tuple, float] = {}
    for m in metas:
        y, mo = _year_month(m)
        if y is None:
            continue
        papers[(y, mo)] = papers.get((y, mo), 0) + 1
        ts = (m or {}).get("topics")
        ts = ts if isinstance(ts, list) else []
        for t in ts:
            if isinstance(t, str) and t:
                k = (y, mo, t)
                topics[k] = topics.get(k, 0.0) + 1.0 / len(ts)
    return {"papers": papers, "topics": topics}


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
               "VALUES (%s, %s::halfvec, %s::jsonb, %s) ON CONFLICT (work_id) DO UPDATE "
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

    def stored_dim(self) -> int | None:
        """Dimension of the stored vectors (vector or halfvec column), None when empty."""
        def q(cur):
            cur.execute("SELECT vector_dims(embedding::vector) FROM paper_embeddings LIMIT 1")
            row = cur.fetchone()
            return int(row[0]) if row and row[0] is not None else None
        return self._run(q)

    def month_counts(self) -> dict[str, int]:
        """Stored papers per month: meta.publication_date, else meta.created."""
        def q(cur):
            cur.execute("SELECT substr(d, 1, 7) m, count(*) FROM (SELECT coalesce(meta->>'publication_date', "
                        "meta->>'created') d FROM paper_embeddings) t "
                        "WHERE d ~ '^[0-9]{4}-[0-9]{2}' GROUP BY 1")
            return {m: int(n) for m, n in cur.fetchall()}
        return self._run(q)

    # One scan of paper_embeddings, two grouping sets: papers per (year, month) and
    # fractional topic counts (1 / topics on the paper) per (year, month, topic).
    # Year/month: publication_date, else pub_year (month NULL), else created.
    _AGG_SQL = """
WITH r AS MATERIALIZED (   -- one detoast of meta per row (jsonb_to_record), not one per field
  SELECT r.publication_date AS pd, r.pub_year AS py, r.created AS cr,
         CASE WHEN jsonb_typeof(r.topics) = 'array' THEN r.topics ELSE '[]'::jsonb END AS ts
  FROM paper_embeddings, jsonb_to_record(meta) AS r(publication_date text, pub_year text, created text, topics jsonb)),
p AS (
  SELECT CASE WHEN pd ~ '^[0-9]{4}-[0-9]{2}' THEN substr(pd, 1, 4)
              WHEN py ~ '^[0-9]{4}$' THEN py
              WHEN cr ~ '^[0-9]{4}-[0-9]{2}' THEN substr(cr, 1, 4) END::int AS y,
         CASE WHEN pd ~ '^[0-9]{4}-[0-9]{2}' THEN substr(pd, 1, 7)
              WHEN py ~ '^[0-9]{4}$' THEN NULL
              WHEN cr ~ '^[0-9]{4}-[0-9]{2}' THEN substr(cr, 1, 7) END AS m,
         ts
  FROM r)
SELECT y, m, t, GROUPING(t) AS g,
       sum(CASE WHEN ord IS NULL OR ord = 1 THEN 1 ELSE 0 END) AS papers,
       sum(CASE WHEN t IS NOT NULL AND t <> '' THEN 1.0 / jsonb_array_length(ts) ELSE 0 END) AS frac
FROM p LEFT JOIN LATERAL jsonb_array_elements_text(ts) WITH ORDINALITY AS e(t, ord) ON true
WHERE y IS NOT NULL
GROUP BY GROUPING SETS ((y, m), (y, m, t))"""

    def aggregate_counts(self) -> dict:
        """Papers per (year, month) and fractional topic counts per (year, month, topic)."""
        def q(cur):
            cur.execute(self._AGG_SQL)
            return cur.fetchall()
        papers, topics = {}, {}
        for y, m, t, g, n, frac in self._run(q):
            if g == 1:
                papers[(int(y), m)] = int(n)
            elif t:
                topics[(int(y), m, t)] = float(frac)
        return {"papers": papers, "topics": topics}

    def ids_missing_publication_date(self) -> list[str]:
        def q(cur):
            cur.execute("SELECT work_id FROM paper_embeddings "
                        "WHERE meta IS NULL OR NOT (meta ? 'publication_date') ORDER BY work_id")
            return [r[0] for r in cur.fetchall()]
        return self._run(q)

    def set_publication_dates(self, dates: dict[str, str | None]) -> int:
        """Metadata-only update: sets meta.publication_date. Vectors and model untouched."""
        rows = [(json.dumps(d), wid) for wid, d in dates.items()]
        if not rows:
            return 0
        with self._connection() as c:
            tx = c.transaction() if hasattr(c, "transaction") else contextlib.nullcontext()
            with tx, c.cursor() as cur:
                cur.executemany(
                    "UPDATE paper_embeddings SET meta = jsonb_set(coalesce(meta, '{}'::jsonb), "
                    "'{publication_date}', %s::jsonb) WHERE work_id = %s", rows)
        return len(rows)

    def put_sampling_rate(self, month: str, openalex_total: int, sampled: int, filter: str) -> None:
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO sampling_rates (month, openalex_total, sampled, filter, fetched_at) "
                "VALUES (%s::date, %s, %s, %s, now()) ON CONFLICT (month) DO UPDATE SET "
                "openalex_total = EXCLUDED.openalex_total, sampled = EXCLUDED.sampled, "
                "filter = EXCLUDED.filter, fetched_at = now()",
                (f"{month}-01", int(openalex_total), int(sampled), filter))

    def sampling_rates(self) -> dict[str, dict]:
        def q(cur):
            cur.execute("SELECT to_char(month, 'YYYY-MM'), openalex_total, sampled, filter, "
                        "fetched_at FROM sampling_rates")
            return cur.fetchall()
        return {m: {"openalex_total": t, "sampled": n, "filter": f, "fetched_at": str(at)}
                for m, t, n, f, at in self._run(q)}

    def database_size(self) -> int:
        def q(cur):
            cur.execute("SELECT pg_database_size(current_database())")
            return int(cur.fetchone()[0])
        return self._run(q)

    # ---- reads ----
    def search(self, query, k=10):
        lit = _vec_literal(query)

        ef = hnsw_ef_search()

        def q(cur):
            conn = getattr(cur, "connection", None)
            tx = conn.transaction() if conn is not None and hasattr(conn, "transaction") \
                else contextlib.nullcontext()
            with tx:   # SET LOCAL only lasts inside a transaction
                cur.execute(f"SET LOCAL hnsw.ef_search = {ef}")
                cur.execute(
                    "SELECT work_id, 1 - (embedding <=> %s::halfvec) AS score, meta "
                    "FROM paper_embeddings ORDER BY embedding <=> %s::halfvec LIMIT %s",
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
            cur.execute("SELECT embedding::vector::text FROM paper_embeddings WHERE work_id = %s", (work_id,))
            return cur.fetchone()
        row = self._run(q)
        return None if not row else np.array(json.loads(row[0]), dtype=np.float32)

    def rows(self):
        def q(cur):
            cur.execute("SELECT work_id, embedding::vector::text, meta FROM paper_embeddings")
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
