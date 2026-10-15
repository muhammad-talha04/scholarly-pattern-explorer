import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "eval"))
import run_search_eval as ev  # noqa: E402

from .conftest import PAPERS


def test_query_set_well_formed():
    qs = ev.load_queries()
    assert len(qs) >= 30 and len({q["id"] for q in qs}) == len(qs)
    for q in qs:
        assert q["query"] and q["keywords"] and isinstance(q["openalex_ids"], list)


def test_grading():
    q = {"keywords": ["protein"], "topics": ["Quantum Computing"], "openalex_ids": ["W3"]}
    m = {p.work_id: p.to_dict() for p in PAPERS}
    assert ev.grade(q, m["W2"]) == 2 and ev.grade(q, m["W3"]) == 2 and ev.grade(q, m["W1"]) == 1


def test_evaluate_runs_on_service(service):
    qs = [{"id": "a", "query": "quantum error correction surface codes", "keywords": ["qubit"],
           "topics": ["Quantum Computing"], "openalex_ids": []},
          {"id": "b", "query": "nothing", "keywords": ["zzz"], "topics": [], "openalex_ids": []}]
    rep = ev.evaluate(service, [p.to_dict() for p in PAPERS], qs, k=1)
    assert rep["scored"] == 1 and rep["per_query"][1]["skipped"]
    assert rep["recall@1"] == 1.0 and rep["ndcg@1"] == 1.0
