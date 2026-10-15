"""Offline checks for eval/score_search.py. No OpenAlex calls."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "eval"))
import score_search as sc  # noqa: E402

from ml.embeddings import HashEmbedder  # noqa: E402
from ml.papers import Paper  # noqa: E402


def test_qrels_file_is_simple_and_covers_queries():
    root = Path(__file__).resolve().parents[2]
    queries = [json.loads(l) for l in (root / "eval" / "search_queries.jsonl").read_text().splitlines() if l.strip()]
    rows = sc.load_qrels(root / "eval" / "search_qrels.jsonl")
    assert len(queries) >= 40
    qids = {q["id"] for q in queries}
    assert len(qids) == len(queries)
    seen = {}
    for row in rows:
        assert set(row) == {"query_id", "query", "work_id", "relevance"}
        assert row["query_id"] in qids
        assert row["query"] and row["work_id"].startswith("W")
        assert row["relevance"] in (0, 1, 2)
        seen.setdefault(row["query_id"], set()).add(row["relevance"])
    assert set(seen) == qids
    assert all(2 in grades and 0 in grades for grades in seen.values())


def test_metrics_match_a_hand_worked_example():
    qrels = [
        {"query_id": "q1", "query": "quantum codes", "work_id": "A", "relevance": 2},
        {"query_id": "q1", "query": "quantum codes", "work_id": "B", "relevance": 1},
        {"query_id": "q1", "query": "quantum codes", "work_id": "C", "relevance": 0},
        {"query_id": "q2", "query": "crops", "work_id": "D", "relevance": 2},
    ]
    # q1 returns the irrelevant paper first. q2 returns its only relevant paper first.
    rankings = {"q1": ["C", "A"], "q2": ["D"]}
    rep = sc.score_rankings(rankings, qrels, ndcg_k=10, recall_k=20)
    assert rep["recall@20"] == 0.75
    assert rep["mrr"] == 0.75
    assert rep["ndcg@10"] == pytest.approx(0.7607, abs=1e-4)


def test_fetch_sends_api_key_and_blocks_a_second_page_without_it(monkeypatch):
    monkeypatch.setattr(sc.time, "sleep", lambda *_a, **_k: None)
    calls = []

    class Resp:
        status_code = 200

        def json(self):
            return {"results": [{
                "id": "https://openalex.org/W1",
                "display_name": "A paper",
                "publication_year": 2020,
            }]}

    class Session:
        def __init__(self):
            self.headers = {}

        def get(self, url, params=None, timeout=None):
            calls.append(params)
            return Resp()

    import requests
    monkeypatch.setattr(requests, "Session", Session)

    monkeypatch.setenv("OPENALEX_API_KEY", "test-key")
    monkeypatch.setenv("OPENALEX_MAILTO", "dev@example.com")
    papers = sc.fetch_openalex(["W1"])
    assert papers[0].work_id == "W1"
    assert calls[0]["api_key"] == "test-key"
    assert calls[0]["mailto"] == "dev@example.com"
    assert calls[0]["per-page"] == "50"

    monkeypatch.delenv("OPENALEX_API_KEY")
    calls.clear()
    sc.fetch_openalex(["W1"])
    assert "api_key" not in calls[0]

    calls.clear()
    with pytest.raises(SystemExit, match="OPENALEX_API_KEY"):
        sc.fetch_openalex([f"W{i}" for i in range(51)])
    assert calls == []


def test_score_runs_repo_search_on_a_fixture():
    papers = [
        Paper("Wrel", "quantum error correction surface codes",
              "Surface codes protect qubits from noise.", 2020, None, ["Quantum Computing"]),
        Paper("Wirr", "wheat yield from satellite imagery",
              "Weather and crops over ten seasons.", 2019, None, ["Agriculture"]),
    ]
    qrels = [
        {"query_id": "q", "query": "quantum error correction", "work_id": "Wrel", "relevance": 2},
        {"query_id": "q", "query": "quantum error correction", "work_id": "Wirr", "relevance": 0},
    ]
    svc = sc.build_service(papers, embedder=HashEmbedder())
    rep = sc.score_service(svc, qrels)
    assert rep["embedder"] == "HashEmbedder"
    assert rep["indexed"] == 2
    assert rep["recall@20"] == 1.0
    assert rep["mrr"] == 1.0
    assert rep["ndcg@10"] == 1.0
    assert rep["per_query"][0]["n_relevant"] == 1
