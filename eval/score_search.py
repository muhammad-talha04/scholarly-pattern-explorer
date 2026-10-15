"""nDCG@10, Recall@20 and MRR for the repo's semantic search.

Judgements live in eval/search_qrels.jsonl. Each line is one graded work:

    {"query_id": "q01", "query": "...", "work_id": "W123", "relevance": 2}

relevance is 0, 1 or 2. A work is relevant when relevance > 0. nDCG uses the
graded gain 2^g - 1, the same gain as eval/run_search_eval.py. Recall and MRR
are binary.

The searcher is ml.service.MLService.search. Relative paths go through
ml.paths.resolve, so the score does not depend on the working directory.

    python eval/score_search.py --works data/works_v2.jsonl
    python eval/score_search.py --fetch          # index the judged works from OpenAlex

`--fetch` loads 50 ids per page. The first page is anonymous. Further pages
need the free OPENALEX_API_KEY (repo secret, already set). The pytest in
ml/tests/test_score_search.py uses an in-memory fixture and does not call
OpenAlex.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.papers import Paper, read_works  # noqa: E402
from ml.paths import resolve  # noqa: E402

HERE = Path(__file__).resolve().parent
QRELS_PATH = HERE / "search_qrels.jsonl"
NDCG_K = 10
RECALL_K = 20


def load_qrels(path: str | Path = QRELS_PATH) -> list[dict]:
    path = Path(path)
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def group_qrels(rows: list[dict]) -> list[dict]:
    """One record per query: text plus work_id -> highest graded relevance."""
    order: list[str] = []
    grouped: dict[str, dict] = {}
    for row in rows:
        qid = row["query_id"]
        if qid not in grouped:
            order.append(qid)
            grouped[qid] = {"query_id": qid, "query": row["query"], "grades": {}}
        wid = row["work_id"]
        rel = int(row["relevance"])
        grouped[qid]["grades"][wid] = max(grouped[qid]["grades"].get(wid, 0), rel)
        if not grouped[qid]["query"]:
            grouped[qid]["query"] = row["query"]
    return [grouped[q] for q in order]


def dcg(gains) -> float:
    return sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(gains))


def ndcg_at_k(ranked_ids: list[str], grades: dict[str, int], k: int) -> float:
    gains = [grades.get(w, 0) for w in ranked_ids[:k]]
    ideal = dcg(sorted(grades.values(), reverse=True)[:k])
    if ideal == 0:
        return 0.0
    return dcg(gains) / ideal


def recall_at_k(ranked_ids: list[str], grades: dict[str, int], k: int) -> float:
    relevant = {w for w, g in grades.items() if g > 0}
    if not relevant:
        return 0.0
    hit = sum(1 for w in ranked_ids[:k] if grades.get(w, 0) > 0)
    return hit / len(relevant)


def reciprocal_rank(ranked_ids: list[str], grades: dict[str, int]) -> float:
    for i, wid in enumerate(ranked_ids, start=1):
        if grades.get(wid, 0) > 0:
            return 1.0 / i
    return 0.0


def score_rankings(rankings: dict[str, list[str]], qrels: list[dict],
                   ndcg_k: int = NDCG_K, recall_k: int = RECALL_K) -> dict:
    """rankings maps query_id -> work ids, best first."""
    per_query = []
    for q in group_qrels(qrels):
        grades = q["grades"]
        if not any(g > 0 for g in grades.values()):
            per_query.append({"query_id": q["query_id"], "skipped": "no relevant judgements"})
            continue
        ranked = rankings.get(q["query_id"], [])
        per_query.append({
            "query_id": q["query_id"],
            f"ndcg@{ndcg_k}": ndcg_at_k(ranked, grades, ndcg_k),
            f"recall@{recall_k}": recall_at_k(ranked, grades, recall_k),
            "rr": reciprocal_rank(ranked, grades),
            "n_relevant": sum(g > 0 for g in grades.values()),
            "n_returned": len(ranked),
        })
    scored = [r for r in per_query if "skipped" not in r]

    def avg(key):
        if not scored:
            return None
        return round(sum(r[key] for r in scored) / len(scored), 4)

    return {
        "queries": len(per_query),
        "scored": len(scored),
        f"ndcg@{ndcg_k}": avg(f"ndcg@{ndcg_k}"),
        f"recall@{recall_k}": avg(f"recall@{recall_k}"),
        "mrr": avg("rr"),
        "per_query": per_query,
    }


def build_service(papers: list[Paper], embedder=None):
    from ml.embeddings import get_embedder
    from ml.service import MLService, SummaryCache
    from ml.store import LocalStore

    tmp = Path(tempfile.mkdtemp(prefix="score-search-"))
    svc = MLService(embedder=embedder or get_embedder(), store=LocalStore(tmp / "vec"),
                    cache=SummaryCache(":memory:"))
    svc.index_papers([p for p in papers if p.text])
    return svc


def rankings_from_service(service, qrels: list[dict], k: int) -> dict[str, list[str]]:
    out = {}
    for q in group_qrels(qrels):
        hits = service.search(q["query"], k=k)
        out[q["query_id"]] = [h["work_id"] for h in hits]
    return out


def score_service(service, qrels: list[dict], ndcg_k: int = NDCG_K, recall_k: int = RECALL_K) -> dict:
    k = max(ndcg_k, recall_k)
    rep = score_rankings(rankings_from_service(service, qrels, k), qrels, ndcg_k, recall_k)
    rep["indexed"] = len(service.store)
    rep["embedder"] = type(service.embedder).__name__
    return rep


def fetch_openalex(work_ids: list[str]) -> list[Paper]:
    """Download judged works from OpenAlex. Not used by tests.

    One page holds 50 ids. A second page is bulk access and requires the
    free OPENALEX_API_KEY (repo secret, already set).
    """
    import requests

    ids = list(dict.fromkeys(work_ids))
    page_size = 50
    api_key = os.environ.get("OPENALEX_API_KEY") or None
    if len(ids) > page_size and not api_key:
        raise SystemExit(
            "OpenAlex bulk fetch past the first page needs OPENALEX_API_KEY "
            "(free; repo secret, already set)")
    papers = []
    mailto = os.environ.get("OPENALEX_MAILTO")
    session = requests.Session()
    session.headers["User-Agent"] = "scholarly-pattern-explorer/score-search"
    for i in range(0, len(ids), page_size):
        chunk = ids[i:i + page_size]
        params = {
            "filter": "openalex:" + "|".join(chunk),
            "per-page": str(page_size),
            "select": ("id,display_name,publication_year,cited_by_count,doi,topics,"
                       "authorships,abstract_inverted_index,open_access,primary_location"),
        }
        if mailto:
            params["mailto"] = mailto
        if api_key:
            params["api_key"] = api_key
        for attempt in range(5):
            resp = session.get("https://api.openalex.org/works", params=params, timeout=60)
            if resp.status_code == 200:
                break
            time.sleep(2 ** attempt)
        else:
            raise SystemExit(f"OpenAlex HTTP {resp.status_code} while fetching judged works")
        for w in resp.json().get("results", []):
            papers.append(Paper.from_openalex(w))
        time.sleep(0.2)
    return papers


def main(argv=None):
    ap = argparse.ArgumentParser(description="Score ml/ search with graded OpenAlex qrels")
    ap.add_argument("--qrels", default=str(QRELS_PATH))
    ap.add_argument("--works", help="works JSONL. Relative paths are from the repo root")
    ap.add_argument("--fetch", action="store_true",
                    help="index the judged work ids from OpenAlex "
                         "(OPENALEX_API_KEY required past the first page of 50)")
    ap.add_argument("--ndcg-k", type=int, default=NDCG_K)
    ap.add_argument("--recall-k", type=int, default=RECALL_K)
    ap.add_argument("--out", help="write the full JSON report here")
    a = ap.parse_args(argv)

    qrels_path = Path(a.qrels)
    if not qrels_path.is_absolute():
        qrels_path = resolve(qrels_path)  # repo root, same rule as ml/paths.py
    qrels = load_qrels(qrels_path)
    if a.fetch:
        ids = [r["work_id"] for r in qrels]
        papers = fetch_openalex(ids)
    else:
        works = resolve(a.works) if a.works else None
        if works is None:
            from ml.papers import default_works_path
            works = default_works_path()
        if works is None or not Path(works).exists():
            sys.exit("no works file. Pass --works data/works_v2.jsonl or --fetch "
                     "(OpenAlex). Tests stay offline and do not need either.")
        papers = list(read_works(works))
    if not papers:
        sys.exit("works file was empty")
    rep = score_service(build_service(papers), qrels, a.ndcg_k, a.recall_k)
    rep["works"] = len(papers)
    if a.out:
        out = resolve(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rep, indent=2), encoding="utf-8")
    summary = {k: v for k, v in rep.items() if k != "per_query"}
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    main()
