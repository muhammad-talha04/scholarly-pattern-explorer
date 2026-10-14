"""Command line entry points (used by cron / GitHub Actions).

  python -m ml.cli index  --jsonl data/works.jsonl         # embed papers
  python -m ml.cli update --jsonl data/works.jsonl         # incremental patterns
  python -m ml.cli update --db data/openalex.duckdb
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .papers import Paper


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield Paper.from_openalex(json.loads(line))


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
