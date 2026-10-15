import pytest

from ml.benchmark import (aggregate, evaluate_embedder, load_papers, load_relevance_csv,
                          recommend, score_ranking)
from ml.embeddings import DEFAULT_MODEL, HashEmbedder, text_prefixes
from ml.paths import REPO_ROOT

QUERIES = REPO_ROOT / "eval" / "benchmark_queries.csv"
PAPERS = REPO_ROOT / "eval" / "benchmark_sample_papers.json"


def test_sample_csv_matches_papers():
    header = QUERIES.read_text(encoding="utf-8").splitlines()[0].strip()
    assert header == "query_id,query,work_id,relevance"
    queries = load_relevance_csv(QUERIES)
    papers = {p.work_id for p in load_papers(PAPERS)}
    assert len(queries) >= 4 and len(papers) > 10
    for query in queries:
        assert query["query"] and any(grade > 0 for grade in query["grades"].values())
        assert set(query["grades"]) <= papers


def test_csv_keeps_max_grade_and_rejects_conflicts(tmp_path):
    path = tmp_path / "q.csv"
    path.write_text("query_id,query,work_id,relevance\n"
                    "q1,alpha,W1,1\nq1,alpha,W1,2\n", encoding="utf-8")
    assert load_relevance_csv(path)[0]["grades"] == {"W1": 2.0}
    path.write_text("query_id,query,work_id,relevance\n"
                    "q1,alpha,W1,1\nq1,beta,W2,1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="conflicting"):
        load_relevance_csv(path)
    path.write_text("query,work_id,relevance\nq,W,1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing columns"):
        load_relevance_csv(path)
    path.write_text("query_id,query,work_id,relevance\nq1,alpha,W1,high\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not a number"):
        load_relevance_csv(path)


def test_recall_and_ndcg():
    scored = score_ranking(["A", "B"], {"A": 2, "C": 2}, k=1)
    assert scored["recall"] == 0.5 and scored["ndcg"] == 1.0
    miss = score_ranking(["B"], {"A": 1}, k=1)
    assert miss["recall"] == 0.0 and miss["ndcg"] == 0.0
    empty = score_ranking(["A"], {"A": 0}, k=10)
    assert empty["recall"] is None and aggregate([{"recall": None, "ndcg": None}], 10)["scored"] == 0


def test_recommend_needs_a_clear_win_on_both_metrics():
    default = {"model": DEFAULT_MODEL, "recall@10": 0.40, "ndcg@10": 0.40}
    close = {"model": "BAAI/bge-small-en-v1.5", "recall@10": 0.44, "ndcg@10": 0.90}
    assert recommend([default, close])["model"] == DEFAULT_MODEL
    win = {"model": "BAAI/bge-small-en-v1.5", "recall@10": 0.50, "ndcg@10": 0.50}
    assert recommend([default, win])["model"] == win["model"]


def test_hash_benchmark_runs_on_the_sample():
    summary = evaluate_embedder(load_papers(PAPERS), load_relevance_csv(QUERIES), HashEmbedder(), k=10)
    assert summary["scored"] == 5
    assert 0.0 <= summary["recall@10"] <= 1.0
    assert 0.0 <= summary["ndcg@10"] <= 1.0
    assert text_prefixes("intfloat/e5-small-v2")["query"] == "query: "
    assert text_prefixes("BAAI/bge-small-en-v1.5")["passage"] == ""
    assert text_prefixes(DEFAULT_MODEL) == {"query": "", "passage": ""}
