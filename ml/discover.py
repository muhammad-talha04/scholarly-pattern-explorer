"""Twice-monthly snapshot of emerging topics and embedding-space gaps.

Reads the incremental stores (topic table or works JSONL, plus the vector index).
Does not rebuild embeddings or patterns.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .emerging import load_topic_rows, rank_emerging
from .paths import ml_data_dir
from .research_gaps import semantic_gaps_from_store


def refresh_discoveries(run_date: str | None = None, *,
                        store=None, snapshot_path=None, db_path=None,
                        works_path=None) -> dict:
    """Write ``data/ml/snapshots/discoveries-<date>.json`` and return a short summary."""
    run_date = run_date or date.today().isoformat()
    rows, source = load_topic_rows(snapshot_path, db_path, works_path)
    emerging = rank_emerging(rows)
    if store is None:
        from .store import get_store
        store = get_store()
    gaps = semantic_gaps_from_store(store)
    payload = {"date": run_date, "topic_source": source,
               "n_emerging": len(emerging), "n_semantic_gaps": len(gaps),
               "emerging": emerging, "semantic_gaps": gaps}
    out = ml_data_dir() / "snapshots" / f"discoveries-{run_date}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload), encoding="utf-8")
    return {"date": run_date, "topic_source": source, "path": str(out),
            "n_emerging": len(emerging), "n_semantic_gaps": len(gaps)}
