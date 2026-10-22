"""Batched, resumable indexer for paper_embeddings.

    python -m ml.cli index --batch-size 1000 --resume      # only work_ids not stored yet
    python -m ml.cli index --reembed                       # replace every row with the current model

Rules
- The embedder always comes from ``ml.embeddings.get_embedder`` (ML_EMBEDDER /
  ML_EMBED_MODEL decide), and every upserted row gets ``model = model_label(embedder)``.
- Refuses to run when the table already holds rows from another model, because
  mixed vector spaces silently break search. ``--reembed`` deletes them all
  and rebuilds with the current model.
- Rows with ``model IS NULL`` predate model tracking. They were written by the
  hash embedder, so they count as ``hash-v1`` only when ML_EMBEDDER=hash; with
  any other embedder they are a different model and block the run.
- Each batch is one transaction (one commit) and logs progress.
- With ``max_db_bytes`` (default 300 MB) it checks ``pg_database_size`` before
  each batch and stops cleanly once the database reaches it (Supabase free tier
  is 500 MB).
- The galaxy is not rebuilt here; ``ml.cli index --galaxy`` or ``ml.cli galaxy`` does that.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from .embeddings import HASH_MODEL_LABEL, get_embedder, model_label

log = logging.getLogger("spe.indexer")
DEFAULT_MAX_DB_BYTES = 300 * 1024 * 1024


class ModelMismatch(RuntimeError):
    pass


@dataclass
class IndexResult:
    model: str
    embedded: int = 0
    skipped_existing: int = 0
    skipped_no_text: int = 0
    batches: int = 0
    stopped_for_size: bool = False
    deleted: int = 0
    notes: list[str] = field(default_factory=list)


def _hash_mode() -> bool:
    return os.getenv("ML_EMBEDDER", "").strip().lower() == "hash"


def stored_models(store) -> dict[str, int]:
    """Model labels in the table. NULL is reported as 'hash-v1' only in hash mode."""
    out: dict[str, int] = {}
    for m, n in (store.model_counts() or {}).items():
        if m is None:
            m = HASH_MODEL_LABEL if _hash_mode() else "<null: legacy, unknown model>"
        out[m] = out.get(m, 0) + n
    return out


def check_models(store, label: str) -> None:
    other = {m: n for m, n in stored_models(store).items() if m != label}
    if other:
        found = ", ".join(f"{m} ({n} rows)" for m, n in sorted(other.items()))
        raise ModelMismatch(
            f"paper_embeddings holds vectors from another model: {found}. "
            f"Current embedder is {label}. Re-run with --reembed to replace every row.")


def index(store, papers, batch_size: int = 1000, resume: bool = True, reembed: bool = False,
          max_db_bytes: int | None = DEFAULT_MAX_DB_BYTES, embedder=None) -> IndexResult:
    embedder = embedder or get_embedder()
    label = model_label(embedder)
    res = IndexResult(model=label)
    if reembed:
        res.deleted = sum((store.model_counts() or {}).values())
        log.warning("reembed: deleting %d existing rows, rebuilding with %s", res.deleted, label)
        store.delete_all_embeddings()
        existing: set[str] = set()
    else:
        check_models(store, label)
        existing = store.existing_ids() if resume else set()

    todo = []
    for p in papers:
        if not p.text:
            res.skipped_no_text += 1
        elif p.work_id in existing:
            res.skipped_existing += 1
        else:
            existing.add(p.work_id)   # duplicate ids in the input are embedded once
            todo.append(p)
    total = len(todo)
    log.info("indexing %d papers with %s (skipped %d existing, %d without text)",
             total, label, res.skipped_existing, res.skipped_no_text)
    encode = getattr(embedder, "encode_documents", None) or embedder.encode
    for i in range(0, total, batch_size):
        if max_db_bytes:
            size = store.database_size()
            if size is not None and size >= max_db_bytes:
                res.stopped_for_size = True
                msg = (f"stopped: database is {size / 2**20:.0f} MB, limit "
                       f"{max_db_bytes / 2**20:.0f} MB; {total - i} papers left")
                res.notes.append(msg)
                log.warning(msg)
                break
        chunk = todo[i:i + batch_size]
        vecs = encode([p.text for p in chunk])
        store.upsert([p.work_id for p in chunk], vecs, [p.to_dict() for p in chunk], model=label)
        res.embedded += len(chunk)
        res.batches += 1
        log.info("batch %d: %d/%d embedded", res.batches, res.embedded, total)
    return res
