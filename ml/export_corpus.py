"""Export the indexed corpus (paper_embeddings.meta) as a works_v2-style JSONL. Read-only.

    DATABASE_URL=... python -m ml.export_corpus --out data/works_live.jsonl

The release `data-store/works_v2.jsonl` is not the live corpus (50,000 works vs the 14,159
in Supabase on 2026-10-16), so a re-embed must take its input from the table itself. Each
line round-trips through ``Paper.from_record`` to the same ``Paper.to_dict()`` meta, so
``ml.cli index --reembed --jsonl <out>`` rewrites the same rows with the new model.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .papers import Paper


def meta_to_v2(meta: dict) -> dict:
    """Stored meta -> v2 row. Keeps publication_date (key presence included) and passes
    every other unmodelled meta key through ``meta_extra`` so a re-embed drops nothing."""
    from .papers import META_KEYS
    row = {"id": meta["work_id"], "title": meta.get("title") or "", "abstract": meta.get("abstract") or "",
            "year": meta.get("pub_year"), "date": meta.get("created"), "doi": meta.get("doi"),
            "topics": meta.get("topics") or [], "authors": meta.get("authors") or [],
            "countries": meta.get("countries") or [], "cited_by": meta.get("cited_by") or 0,
            "original_url": meta.get("original_url")}
    if "publication_date" in meta:
        row["publication_date"] = meta["publication_date"]
    extra = {k: v for k, v in meta.items() if k not in META_KEYS}
    if extra:
        row["meta_extra"] = extra
    return row


def export(store, out: str | Path) -> int:
    ids, _vecs, metas = store.rows()
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(out, "w", encoding="utf-8") as f:
        for wid, meta in sorted(zip(ids, metas), key=lambda x: x[0]):
            meta = dict(meta or {}, work_id=meta.get("work_id") or wid)
            row = meta_to_v2(meta)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    return n


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    from .store import get_store
    print(f"exported {export(get_store(), a.out)} papers to {a.out}")


if __name__ == "__main__":
    main()
