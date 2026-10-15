"""Compare embedding models with recall@k and nDCG@k.

The labelled file is CSV with columns ``query_id,query,work_id,relevance``.
``relevance`` is a numeric grade (higher is more relevant). A grade above 0
counts as relevant for recall. Papers omitted from a query are grade 0.
Several rows share a query_id; the query text must agree. A repeated work id
keeps the higher grade.

    python -m ml.benchmark
    python -m ml.benchmark --queries eval/benchmark_queries.csv --papers eval/benchmark_sample_papers.json
    ML_EMBEDDER=hash python -m ml.benchmark          # offline smoke, scores are meaningless

A replacement model is recommended only when it beats all-MiniLM-L6-v2 by at
least 0.05 on both recall@k and nDCG@k. The checked-in sample is a format
example for a later hand-labelled set, not that set.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import tempfile
import time
from pathlib import Path

from .embeddings import CANDIDATE_MODELS, DEFAULT_MODEL, Embedder, HashEmbedder
from .papers import Paper, read_works
from .paths import REPO_ROOT
from .service import MLService, SummaryCache
from .store import LocalStore

REQUIRED_COLUMNS = ("query_id", "query", "work_id", "relevance")
CLEAR_WIN_MARGIN = 0.05


def dcg(gains) -> float:
    return sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(gains))


def load_relevance_csv(path: str | Path) -> list[dict]:
    """Group a query/relevance CSV into ``{id, query, grades}`` records."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("relevance CSV is empty")
        canon = {header.strip(): header for header in reader.fieldnames if header}
        missing = [col for col in REQUIRED_COLUMNS if col not in canon]
        if missing:
            raise ValueError("relevance CSV missing columns: " + ", ".join(missing))
        grouped: dict[str, dict] = {}
        order: list[str] = []
        for raw in reader:
            row = {col: (raw.get(canon[col]) or "").strip() for col in REQUIRED_COLUMNS}
            qid = row["query_id"]
            if not qid:
                continue
            if qid not in grouped:
                grouped[qid] = {"id": qid, "query": row["query"], "grades": {}}
                order.append(qid)
            elif row["query"] and row["query"] != grouped[qid]["query"]:
                raise ValueError(f"query_id {qid} has conflicting query text")
            if not row["work_id"]:
                continue
            try:
                grade = float(row["relevance"])
            except ValueError as exc:
                raise ValueError(f"relevance for {qid}/{row['work_id']} is not a number") from exc
            prev = grouped[qid]["grades"].get(row["work_id"])
            if prev is None or grade > prev:
                grouped[qid]["grades"][row["work_id"]] = grade
    return [grouped[qid] for qid in order]


def score_ranking(retrieved: list[str], grades: dict[str, float], k: int) -> dict:
    """recall@k and nDCG@k. None when the query has no positive grade."""
    relevant = {wid for wid, grade in grades.items() if grade > 0}
    if not relevant:
        return {"recall": None, "ndcg": None}
    top = list(retrieved)[:k]
    recall = len({wid for wid in top if grades.get(wid, 0) > 0}) / len(relevant)
    gains = [float(grades.get(wid, 0.0)) for wid in top]
    ideal = sorted((float(g) for g in grades.values() if g > 0), reverse=True)[:k]
    ideal_dcg = dcg(ideal)
    ndcg = dcg(gains) / ideal_dcg if ideal_dcg else 0.0
    return {"recall": recall, "ndcg": ndcg}


def aggregate(per_query: list[dict], k: int) -> dict:
    scored = [row for row in per_query if row.get("recall") is not None]
    def avg(key):
        return round(sum(row[key] for row in scored) / len(scored), 4) if scored else None
    return {"k": k, "queries": len(per_query), "scored": len(scored),
            f"recall@{k}": avg("recall"), f"ndcg@{k}": avg("ndcg")}


def load_papers(path: str | Path) -> list[Paper]:
    path = Path(path)
    if path.suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data["papers"] if isinstance(data, dict) else data
        papers = []
        for row in rows:
            if "abstract_inverted_index" in row or "publication_year" in row:
                papers.append(Paper.from_record(row))
            elif "id" in row and "work_id" not in row and "year" in row:
                papers.append(Paper(work_id=row["id"], title=row.get("title") or "",
                                    abstract=row.get("abstract") or "", pub_year=row.get("year"),
                                    topics=row.get("topics") or []))
            else:
                papers.append(Paper.from_record(row))
        return papers
    return list(read_works(path))


def evaluate_embedder(papers: list[Paper], queries: list[dict], embedder, k: int = 10) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="embed-bench-"))
    service = MLService(embedder=embedder, store=LocalStore(tmp / "vec"),
                        cache=SummaryCache(":memory:"), galaxy_dir=tmp / "galaxy")
    service.index_papers(papers)
    per_query = []
    for query in queries:
        hits = service.search(query["query"], k=k)
        scored = score_ranking([hit["work_id"] for hit in hits], query["grades"], k)
        per_query.append({"query_id": query["id"], **scored})
    summary = aggregate(per_query, k)
    summary["per_query"] = per_query
    return summary


def recommend(results: list[dict], default: str = DEFAULT_MODEL, k: int = 10,
              margin: float = CLEAR_WIN_MARGIN) -> dict:
    """Keep the default unless another model wins by ``margin`` on both metrics."""
    recall_key, ndcg_key = f"recall@{k}", f"ndcg@{k}"
    ok = [row for row in results if "error" not in row and row.get(recall_key) is not None
          and row.get(ndcg_key) is not None]
    base = next((row for row in ok if row.get("model") == default), None)
    if base is None:
        return {"model": default, "reason": "keep the default; it was not scored"}
    best = max(ok, key=lambda row: (row[ndcg_key], row[recall_key]))
    if (best["model"] != default and best[recall_key] >= base[recall_key] + margin
            and best[ndcg_key] >= base[ndcg_key] + margin):
        return {"model": best["model"],
                "reason": f"clear win over {default} by at least {margin} on both metrics"}
    return {"model": default, "reason": "no clear win on both recall and nDCG; keep the default"}


def run_benchmark(papers: list[Paper], queries: list[dict], models: list[str], k: int = 10,
                  hash_embedder: bool = False) -> dict:
    results = []
    if hash_embedder:
        started = time.perf_counter()
        try:
            summary = evaluate_embedder(papers, queries, HashEmbedder(), k=k)
            summary.pop("per_query", None)
            results.append({"model": "hash", "seconds": round(time.perf_counter() - started, 2), **summary})
        except Exception as exc:
            results.append({"model": "hash", "error": str(exc)})
    else:
        for name in models:
            started = time.perf_counter()
            try:
                summary = evaluate_embedder(papers, queries, Embedder(name), k=k)
                per_query = summary.pop("per_query")
                results.append({"model": name, "seconds": round(time.perf_counter() - started, 2),
                                **summary, "per_query": per_query})
            except Exception as exc:
                results.append({"model": name, "error": str(exc)})
    public = []
    for row in results:
        item = {key: value for key, value in row.items() if key != "per_query"}
        public.append(item)
    return {"k": k, "default": DEFAULT_MODEL, "margin": CLEAR_WIN_MARGIN,
            "papers": len(papers), "results": public,
            "recommendation": recommend(public, k=k),
            "details": results}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Compare free embedding models on a labelled CSV")
    ap.add_argument("--queries", default=str(REPO_ROOT / "eval" / "benchmark_queries.csv"))
    ap.add_argument("--papers", default=str(REPO_ROOT / "eval" / "benchmark_sample_papers.json"))
    ap.add_argument("--models", nargs="*", default=list(CANDIDATE_MODELS))
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--out")
    ap.add_argument("--hash", action="store_true", help="score the offline hash embedder only")
    args = ap.parse_args(argv)
    papers = load_papers(args.papers)
    queries = load_relevance_csv(args.queries)
    if not papers or not queries:
        raise SystemExit("papers and queries are both required")
    use_hash = args.hash or os.getenv("ML_EMBEDDER", "").lower() == "hash"
    report = run_benchmark(papers, queries, args.models, k=args.k, hash_embedder=use_hash)
    shown = {key: value for key, value in report.items() if key != "details"}
    text = json.dumps(shown, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    main()
