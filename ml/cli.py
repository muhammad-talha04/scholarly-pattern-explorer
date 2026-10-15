"""Command line entry points (used by cron / GitHub Actions).

  python -m ml.cli index                                   # embed data/works_v2.jsonl
  python -m ml.cli index --model BAAI/bge-small-en-v1.5   # a different free model
  python -m ml.cli galaxy                                  # layout from the current index
  python -m ml.cli galaxy --refit                          # recompute layout (points may move)
  python -m ml.cli update                                  # incremental patterns, then discoveries
  python -m ml.cli discover                                # emerging topics + embedding gaps only
  python -m ml.cli index  --jsonl data/works.jsonl         # old JSONL fallback
  python -m ml.cli update --db data/openalex.duckdb
"""
from __future__ import annotations

import argparse
import os

from .embeddings import Embedder, get_embedder
from .papers import read_works
from .paths import ml_data_dir


def read_jsonl(path=None):
    """data/works_v2.jsonl by default; old OpenAlex-shaped JSONL still works."""
    return read_works(path)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["index", "update", "galaxy", "discover"])
    ap.add_argument("--jsonl")
    ap.add_argument("--db")
    ap.add_argument("--model", help="sentence-transformers model id (ignored when ML_EMBEDDER=hash)")
    ap.add_argument("--refit", action="store_true", help="recompute the galaxy layout from scratch")
    ap.add_argument("--min-support", type=float, default=0.05)
    ap.add_argument("--window", type=int, default=3)
    a = ap.parse_args(argv)
    if a.cmd == "discover":
        from .discover import refresh_discoveries
        print(refresh_discoveries())
        return
    if a.cmd in ("index", "galaxy"):
        from .service import MLService
        if os.getenv("ML_EMBEDDER", "").lower() == "hash" or not a.model:
            embedder = get_embedder()
        else:
            embedder = Embedder(a.model)
        svc = MLService(embedder=embedder)
        if a.cmd == "index":
            n = svc.index_papers(list(read_jsonl(a.jsonl)))
            print(f"indexed {n} papers")
        points = svc.galaxy(refit=a.refit)
        print(f"galaxy {len(points)} points")
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


if __name__ == "__main__":
    main()
