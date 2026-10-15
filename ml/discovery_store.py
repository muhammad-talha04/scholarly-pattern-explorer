"""Read and write the discoveries snapshot.

The scheduled discover step calls ``save_discoveries``. The API calls
``load_discoveries`` and does not recompute. Both sides use only these two
functions so they can later move onto the shared pgvector/Supabase store
(with the same local file as the fallback) without changing callers.
"""
from __future__ import annotations

import json
from pathlib import Path

from .paths import discoveries_path


def save_discoveries(payload: dict, path: str | Path | None = None) -> Path:
    """Write the latest snapshot and a dated copy next to it."""
    path = Path(path) if path else discoveries_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload)
    path.write_text(body, encoding="utf-8")
    dated = path.parent / "snapshots" / f"discoveries-{payload.get('date') or 'undated'}.json"
    dated.parent.mkdir(parents=True, exist_ok=True)
    dated.write_text(body, encoding="utf-8")
    return path


def load_discoveries(path: str | Path | None = None) -> dict | None:
    """Return the latest snapshot, or None when discover has not run yet."""
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
