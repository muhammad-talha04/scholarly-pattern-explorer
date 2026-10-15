"""Read and write the discoveries snapshot.

The scheduled discover step calls ``save_discoveries``. The API calls
``load_discoveries`` and does not recompute.

When the shared store is Postgres (``DATABASE_URL`` set, and
``ML_VECTOR_BACKEND`` is not ``local``), rows go in ``discovery_snapshots``
with the migration columns ``run_date``, ``kind``, ``country_code``,
``results``, and ``created_at``. The same run also writes the local JSON file
so the twice-monthly release can upload it. Otherwise only the file is used.
``ML_VECTOR_BACKEND=local`` keeps the file even if ``DATABASE_URL`` is set,
matching ``ml.store.get_store``.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

from .paths import discoveries_path

# Columns written on every insert. ``id`` is bigserial and stays unset.
_INSERT = (
    "INSERT INTO discovery_snapshots (run_date, kind, country_code, results, created_at) "
    "VALUES (%s, %s, %s, %s::jsonb, %s)"
)
_SELECT_LATEST = (
    "SELECT kind, country_code, results, run_date::text "
    "FROM discovery_snapshots "
    "WHERE created_at = (SELECT max(created_at) FROM discovery_snapshots)"
)


def _use_database() -> bool:
    """Same switch as ``get_store``: Postgres unless the backend is forced local."""
    backend = os.getenv("ML_VECTOR_BACKEND", "").strip().lower()
    if backend == "local":
        return False
    return backend == "pgvector" or bool(os.getenv("DATABASE_URL"))


def _connection():
    """Postgres connection from the shared store. Migrations run on connect."""
    from .store import get_store
    store = get_store()
    conn = getattr(store, "conn", None)
    if conn is None:
        raise RuntimeError("discovery snapshots need the Postgres store")
    return conn


def _run_date(payload: dict) -> str:
    raw = str(payload.get("date") or "").strip()
    if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
        return raw[:10]
    return date.today().isoformat()


def _snapshot_rows(payload: dict) -> list[tuple[str, str, str | None, object]]:
    """One tuple per ``discovery_snapshots`` row: run_date, kind, country_code, results."""
    run_date = _run_date(payload)
    rows: list[tuple[str, str, str | None, object]] = [
        (run_date, "gap", None, list(payload.get("gaps") or [])),
        (run_date, "emerging", None, list(payload.get("emerging") or [])),
    ]
    for code, items in sorted((payload.get("emerging_by_country") or {}).items()):
        country = str(code or "").strip().upper()
        if country:
            rows.append((run_date, "emerging", country, list(items or [])))
    if "semantic_gaps" in payload:
        rows.append((run_date, "semantic_gaps", None, list(payload.get("semantic_gaps") or [])))
    if "similar" in payload:
        rows.append((run_date, "similar", None, payload.get("similar") or {}))
    emerging = payload.get("emerging") or []
    semantic = payload.get("semantic_gaps") or []
    rows.append((run_date, "run", None, {
        "topic_source": payload.get("topic_source"),
        "n_emerging": payload.get("n_emerging", len(emerging)),
        "n_semantic_gaps": payload.get("n_semantic_gaps", len(semantic)),
    }))
    return rows


def _as_json(value):
    if isinstance(value, str):
        return json.loads(value)
    return value


def _payload_from_rows(rows: list[tuple]) -> dict | None:
    """Rebuild the snapshot dict the API already reads."""
    if not rows:
        return None
    gaps = None
    emerging = None
    by_country: dict = {}
    semantic = None
    similar = None
    run: dict = {}
    run_date = None
    for kind, country, results, when in rows:
        results = _as_json(results)
        run_date = when or run_date
        if kind == "gap":
            gaps = results
        elif kind == "emerging" and country:
            by_country[str(country).strip().upper()] = results
        elif kind == "emerging":
            emerging = results
        elif kind == "semantic_gaps":
            semantic = results
        elif kind == "similar" and isinstance(results, dict):
            similar = results
        elif kind == "run" and isinstance(results, dict):
            run = results
    if gaps is None and emerging is None and semantic is None and similar is None and not by_country:
        return None
    payload = {
        "date": str(run_date)[:10] if run_date else None,
        "topic_source": run.get("topic_source"),
        "n_emerging": run.get("n_emerging", len(emerging or [])),
        "n_semantic_gaps": run.get("n_semantic_gaps", len(semantic or [])),
        "gaps": list(gaps or []),
        "emerging": list(emerging or []),
        "emerging_by_country": by_country,
    }
    if semantic is not None:
        payload["semantic_gaps"] = list(semantic)
    if similar is not None:
        payload["similar"] = similar
    return payload


def _save_database(payload: dict) -> None:
    created_at = datetime.now(timezone.utc)
    conn = _connection()
    with conn.cursor() as cur:
        for run_date, kind, country, results in _snapshot_rows(payload):
            cur.execute(_INSERT, (run_date, kind, country, json.dumps(results), created_at))


def _load_database() -> dict | None:
    conn = _connection()
    with conn.cursor() as cur:
        cur.execute(_SELECT_LATEST)
        fetched = cur.fetchall()
    return _payload_from_rows(list(fetched))


def _save_file(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload)
    path.write_text(body, encoding="utf-8")
    dated = path.parent / "snapshots" / f"discoveries-{payload.get('date') or 'undated'}.json"
    dated.parent.mkdir(parents=True, exist_ok=True)
    dated.write_text(body, encoding="utf-8")


def save_discoveries(payload: dict, path: str | Path | None = None) -> Path:
    """Write the latest snapshot.

    An explicit ``path`` is the local file only (tests). The default path
    follows the shared store: Postgres rows plus the release file, or the
    file alone when the store is local.
    """
    explicit = path is not None
    path = Path(path) if path else discoveries_path()
    if not explicit and _use_database():
        _save_database(payload)
    _save_file(payload, path)
    return path


def load_discoveries(path: str | Path | None = None) -> dict | None:
    """Return the latest snapshot, or None when discover has not run yet.

    With no ``path``, a Postgres store is read from ``discovery_snapshots``.
    A path, or a local store, reads the JSON file.
    """
    if path is None and _use_database():
        return _load_database()
    path = Path(path) if path else discoveries_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data
