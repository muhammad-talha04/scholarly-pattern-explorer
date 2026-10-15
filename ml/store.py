"""Vector storage: pgvector (Supabase) or a local FAISS / numpy fallback.

All vectors are L2-normalised, so cosine similarity == inner product.

The same store holds JSON documents (the precomputed galaxy, pattern snapshots,
country and topic counts). Postgres is used when ``DATABASE_URL`` is set, unless
``ML_VECTOR_BACKEND=local``. Otherwise documents are JSON files next to the
vectors, so tests run with no database.
"""
from __future__ import annotations

import json
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
    def upsert(self, ids: list[str], vectors: np.ndarray, meta: list[dict]) -> None: ...
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
        if self.path and (self.path / "vectors.npy").exists():
            self.vecs = np.load(self.path / "vectors.npy")
            self.dim = int(self.vecs.shape[1])
            data = json.loads((self.path / "meta.json").read_text(encoding="utf-8"))
            self.ids, self.meta = data["ids"], data["meta"]
        if self.path and (self.path / "documents").is_dir():
            for f in sorted((self.path / "documents").glob("*.json")):
                if _KIND.fullmatch(f.stem):
                    self._docs[f.stem] = json.loads(f.read_text(encoding="utf-8"))

    def __len__(self):
        return len(self.ids)

    def rows(self):
        return list(self.ids), self.vecs, [self.meta.get(i, {}) for i in self.ids]

    def upsert(self, ids, vectors, meta):
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
        (self.path / "meta.json").write_text(json.dumps({"ids": self.ids, "meta": self.meta}),
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


class PgVectorStore:
    """Supabase Postgres + pgvector. Needs psycopg (v3) and DATABASE_URL.

    Connecting applies every file in ``db/migrations`` in order. The same files
    are what ``python -m db.apply`` runs.
    """

    def __init__(self, dsn: str | None = None, conn=None):
        if conn is None:
            import psycopg
            conn = psycopg.connect(dsn or os.environ["DATABASE_URL"], autocommit=True)
        self.conn = conn
        with self.conn.cursor() as cur:
            for stmt in migration_sql():
                cur.execute(stmt)

    def __len__(self):
        with self.conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM paper_embeddings")
            return cur.fetchone()[0]

    def upsert(self, ids, vectors, meta):
        with self.conn.cursor() as cur:
            for wid, v, m in zip(ids, vectors, meta):
                cur.execute(
                    "INSERT INTO paper_embeddings (work_id, embedding, meta) "
                    "VALUES (%s, %s::vector, %s::jsonb) ON CONFLICT (work_id) DO UPDATE "
                    "SET embedding = EXCLUDED.embedding, meta = EXCLUDED.meta",
                    (wid, _vec_literal(v), json.dumps(m)))

    def search(self, query, k=10):
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT work_id, 1 - (embedding <=> %s::vector) AS score, meta "
                "FROM paper_embeddings ORDER BY embedding <=> %s::vector LIMIT %s",
                (_vec_literal(query), _vec_literal(query), k))
            rows = cur.fetchall()
        return [(w, float(s), m if isinstance(m, dict) else json.loads(m)) for w, s, m in rows]

    def get(self, work_id):
        with self.conn.cursor() as cur:
            cur.execute("SELECT meta FROM paper_embeddings WHERE work_id = %s", (work_id,))
            row = cur.fetchone()
        if not row:
            return None
        return row[0] if isinstance(row[0], dict) else json.loads(row[0])

    def vector(self, work_id):
        with self.conn.cursor() as cur:
            cur.execute("SELECT embedding::text FROM paper_embeddings WHERE work_id = %s", (work_id,))
            row = cur.fetchone()
        return None if not row else np.array(json.loads(row[0]), dtype=np.float32)

    def rows(self):
        with self.conn.cursor() as cur:
            cur.execute("SELECT work_id, embedding::text, meta FROM paper_embeddings")
            fetched = cur.fetchall()
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
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO documents (kind, payload, updated_at) VALUES (%s, %s::jsonb, now()) "
                "ON CONFLICT (kind) DO UPDATE SET payload = EXCLUDED.payload, updated_at = now()",
                (kind, json.dumps(payload)))

    def get_document(self, kind: str) -> dict | None:
        kind = check_kind(kind)
        with self.conn.cursor() as cur:
            cur.execute("SELECT payload FROM documents WHERE kind = %s", (kind,))
            row = cur.fetchone()
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
