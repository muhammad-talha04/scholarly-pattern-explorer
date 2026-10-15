"""Recall@k and nDCG@k of ml/ semantic search against eval/search_queries.jsonl.

    ML_EMBEDDER=hash python eval/run_search_eval.py --works data/works_v2.jsonl   # offline smoke
    python eval/run_search_eval.py --works data/works_v2.jsonl --k 10             # real MiniLM

Relevance is graded from the corpus itself (no hand-labelled IDs yet):
  2 = paper is in the work's listed OpenAlex IDs, or carries one of the query's topics
  1 = title has a query keyword, or the abstract has >= 2 distinct query keywords
  0 = otherwise
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml.papers import read_works  # noqa: E402

HERE = Path(__file__).resolve().parent


def load_queries(path=HERE / "search_queries.jsonl") -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def grade(q: dict, meta: dict) -> int:
    if meta.get("work_id") in set(q.get("openalex_ids") or []):
        return 2
    if set(q.get("topics") or []) & set(meta.get("topics") or []):
        return 2
    kws = [k.lower() for k in q.get("keywords") or []]
    title, abstract = (meta.get("title") or "").lower(), (meta.get("abstract") or "").lower()
    if any(k in title for k in kws) or sum(k in abstract for k in kws) >= 2:
        return 1
    return 0


def dcg(gains) -> float:
    return sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(gains))


def evaluate(service, papers: list[dict], queries: list[dict], k: int = 10) -> dict:
    rows = []
    for q in queries:
        all_grades = [grade(q, m) for m in papers]
        n_rel = sum(g > 0 for g in all_grades)
        if n_rel == 0:
            rows.append({"id": q["id"], "skipped": "no relevant papers in corpus"})
            continue
        hits = service.search(q["query"], k=k)
        gains = [grade(q, h | {"abstract": (service.get_paper(h["work_id"]) or {}).get("abstract")})
                 for h in hits]
        ideal = dcg(sorted(all_grades, reverse=True)[:k])
        rows.append({"id": q["id"], "recall": sum(g > 0 for g in gains) / n_rel,
                     "recall_capped": sum(g > 0 for g in gains) / min(n_rel, k),
                     "ndcg": dcg(gains) / ideal if ideal else 0.0, "n_relevant": n_rel})
    scored = [r for r in rows if "skipped" not in r]
    avg = (lambda key: round(sum(r[key] for r in scored) / len(scored), 4)) if scored else (lambda key: None)
    return {"k": k, "queries": len(queries), "scored": len(scored),
            f"recall@{k}": avg("recall"), f"recall_capped@{k}": avg("recall_capped"),
            f"ndcg@{k}": avg("ndcg"), "per_query": rows}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--works", help="works JSONL (default: data/works_v2.jsonl or old JSONL)")
    ap.add_argument("--queries", default=str(HERE / "search_queries.jsonl"))
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--out", help="write full JSON report here")
    a = ap.parse_args(argv)
    from ml.service import MLService, SummaryCache
    from ml.store import LocalStore
    papers = list(read_works(a.works))
    if not papers:
        sys.exit("no works found; pass --works")
    tmp = Path(tempfile.mkdtemp(prefix="search-eval-"))
    svc = MLService(store=LocalStore(tmp / "vec"), cache=SummaryCache(":memory:"))
    svc.index_papers(papers)
    rep = evaluate(svc, [p.to_dict() for p in papers], load_queries(a.queries), a.k)
    if a.out:
        Path(a.out).write_text(json.dumps(rep, indent=2))
    print(json.dumps({k: v for k, v in rep.items() if k != "per_query"}, indent=2))


if __name__ == "__main__":
    main()
