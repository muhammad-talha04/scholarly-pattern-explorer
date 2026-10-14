"""Command line entry points (used by cron / GitHub Actions).

  python -m ml.cli index                                   # embed data/works_v2.jsonl
  python -m ml.cli update                                  # incremental patterns
  python -m ml.cli index  --jsonl data/works.jsonl         # old JSONL fallback
  python -m ml.cli update --db data/openalex.duckdb
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from .papers import read_works


def read_jsonl(path=None):
    """data/works_v2.jsonl by default; old OpenAlex-shaped JSONL still works."""
    return read_works(path)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["index", "update"])
    ap.add_argument("--jsonl")
    ap.add_argument("--db")
    ap.add_argument("--min-support", type=float, default=0.05)
    ap.add_argument("--window", type=int, default=3)
    a = ap.parse_args(argv)
    if a.cmd == "index":
        from .service import MLService
        n = MLService().index_papers(list(read_jsonl(a.jsonl)))
        print(f"indexed {n} papers")
        return
    from .incremental import IncrementalMiner, papers_since_from_db
    miner = IncrementalMiner(Path(os.getenv("ML_DATA_DIR", "data/ml")) / "patterns",
                             window=a.window, min_support=a.min_support)
    if a.db:
        from dbconn import DB
        papers = papers_since_from_db(DB(a.db))
    else:
        papers = [p.to_dict() for p in read_jsonl(a.jsonl)]
    print(miner.update(papers))


if __name__ == "__main__":
    main()
