"""Command line entry points (used by cron / GitHub Actions).

  python -m ml.cli index --batch-size 1000 --resume        # embed only work_ids not stored yet
  python -m ml.cli index --reembed                         # replace all rows with the current model
  python -m ml.cli index --galaxy                          # index, then rebuild the galaxy
  python -m ml.cli index --model BAAI/bge-small-en-v1.5   # a different free model
  python -m ml.cli galaxy                                  # store the galaxy graph from the index
  python -m ml.cli galaxy --refit                          # recompute layout (points may move)
  python -m ml.cli update                                  # incremental patterns, then discoveries
  python -m ml.cli discover                                # emerging topics + embedding gaps only
  python -m ml.cli index  --jsonl data/works.jsonl         # old JSONL fallback
  python -m ml.cli update --db data/openalex.duckdb
  python -m ml.cli backfill-dates [--dry-run] [--batch 50]  # meta.publication_date from OpenAlex
  python -m ml.cli bulk --target 70000 --start 2015-01 [--index]  # stratified OpenAlex fetch (ml/bulk.py)
"""
from __future__ import annotations

import argparse

from .embeddings import get_embedder
from .papers import read_works
from .paths import ml_data_dir


def read_jsonl(path=None):
    """data/works_v2.jsonl by default; old OpenAlex-shaped JSONL still works."""
    return read_works(path)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["index", "update", "galaxy", "discover", "bulk", "backfill-dates"])
    ap.add_argument("--jsonl")
    ap.add_argument("--db")
    ap.add_argument("--model", help="sentence-transformers model id (ignored when ML_EMBEDDER=hash)")
    ap.add_argument("--refit", action="store_true", help="recompute the galaxy layout from scratch")
    ap.add_argument("--min-support", type=float, default=0.05)
    ap.add_argument("--window", type=int, default=3)
    ap.add_argument("--batch-size", type=int, default=1000)
    ap.add_argument("--resume", action="store_true", default=True,
                    help="skip work_ids already in paper_embeddings (default)")
    ap.add_argument("--no-resume", dest="resume", action="store_false")
    ap.add_argument("--reembed", action="store_true",
                    help="delete every stored vector and re-embed all with the current model")
    ap.add_argument("--max-db-mb", type=float, default=300,
                    help="stop before a batch once pg_database_size reaches this (0 = off)")
    ap.add_argument("--galaxy", action="store_true", help="index: rebuild the galaxy afterwards")
    ap.add_argument("--target", type=int, default=70000, help="bulk: papers to fetch")
    ap.add_argument("--start", default="2015-01", help="bulk: first month YYYY-MM")
    ap.add_argument("--end", default=None, help="bulk: last month YYYY-MM (default now)")
    ap.add_argument("--out", default="data/bulk_works.jsonl", help="bulk: JSONL checkpoint")
    ap.add_argument("--index", action="store_true", help="bulk: embed + upsert after fetching")
    ap.add_argument("--min-abstract-chars", type=int, default=200, help="bulk: skip shorter abstracts")
    ap.add_argument("--dry-run", action="store_true", help="backfill-dates: only count")
    ap.add_argument("--batch", type=int, default=50, help="backfill-dates: ids per OpenAlex request")
    a = ap.parse_args(argv)
    if a.cmd == "backfill-dates":
        import logging
        from .bulk import backfill_dates
        from .store import get_store
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
        r = backfill_dates(get_store(), batch=a.batch, dry_run=a.dry_run)
        print(f"{r.missing} papers missing publication_date"
              + ("" if a.dry_run else f"; updated {r.updated}, not in OpenAlex {r.not_found}, "
                 f"{r.requests} requests"))
        return
    if a.cmd == "bulk":
        import logging
        from .bulk import fetch
        from .indexer import ModelMismatch, check_models, index
        from .embeddings import model_label
        from .store import get_store
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
        store = get_store()
        embedder = get_embedder(a.model)
        if a.index:   # refuse before spending an hour fetching
            try:
                check_models(store, model_label(embedder))
            except ModelMismatch as exc:
                raise SystemExit(str(exc))
        r = fetch(a.target, a.out, start=a.start, end=a.end, exclude_ids=store.existing_ids(),
                  existing_by_month=store.month_counts(), min_abstract_chars=a.min_abstract_chars,
                  rates_sink=store.put_sampling_rate)
        print(f"fetched {r.fetched} new papers in {r.requests} requests; short months: {len(r.short_months)}")
        if a.index:
            try:
                res = index(store, read_jsonl(a.out), batch_size=a.batch_size, resume=True,
                            embedder=embedder, max_db_bytes=int(a.max_db_mb * 2**20) or None)
            except ModelMismatch as exc:
                raise SystemExit(str(exc))
            print(f"indexed {res.embedded} papers with {res.model}"
                  + ("; STOPPED at size limit" if res.stopped_for_size else ""))
        return
    if a.cmd == "discover":
        from .discover import refresh_discoveries
        print(refresh_discoveries())
        return
    if a.cmd in ("index", "galaxy"):
        from .service import MLService
        embedder = get_embedder(a.model)   # ML_EMBEDDER=hash wins over --model
        svc = MLService(embedder=embedder)
        if a.cmd == "index":
            import logging
            from .indexer import ModelMismatch, index
            logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
            try:
                res = index(svc.store, read_jsonl(a.jsonl), batch_size=a.batch_size,
                            resume=a.resume, reembed=a.reembed, embedder=embedder,
                            max_db_bytes=int(a.max_db_mb * 2**20) or None)
            except ModelMismatch as exc:
                raise SystemExit(str(exc))
            print(f"indexed {res.embedded} papers with {res.model} in {res.batches} batches; "
                  f"skipped {res.skipped_existing} existing"
                  + ("; STOPPED at size limit" if res.stopped_for_size else ""))
            if not a.galaxy:
                return
        graph = svc.rebuild_galaxy(refit=a.refit)
        print(f"galaxy {len(graph['nodes'])} nodes")
        return
    from .incremental import IncrementalMiner, papers_since_from_db
    miner = IncrementalMiner(ml_data_dir() / "patterns",
                             window=a.window, min_support=a.min_support)
    if a.db:
        from dbconn import DB
        papers = papers_since_from_db(DB(a.db))
    else:
        papers = [p.to_dict() for p in read_jsonl(a.jsonl)]
    summary = miner.update(papers)
    print(summary)
    # Pattern state is already saved. A discovery failure must not fail that update.
    try:
        from .discover import refresh_discoveries
        print(refresh_discoveries(summary.get("run_date")))
    except Exception as exc:
        print(f"discoveries skipped: {exc}")
    # The pattern snapshot is already saved. A galaxy failure must not undo that.
    try:
        from .service import MLService
        graph = MLService().rebuild_galaxy()
        print(f"galaxy {len(graph['nodes'])} nodes")
    except Exception as exc:
        print(f"galaxy skipped: {exc}")


if __name__ == "__main__":
    main()
