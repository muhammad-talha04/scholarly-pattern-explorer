import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import ml_bridge
from app.main import app

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from ml.embeddings import HashEmbedder  # noqa: E402
from ml.incremental import IncrementalMiner  # noqa: E402
from ml.papers import Paper  # noqa: E402
from ml.service import MLService, SummaryCache  # noqa: E402
from ml.store import LocalStore  # noqa: E402

V2 = [
    {"id": "W1", "title": "Transformers for protein structure prediction", "year": 2021,
     "abstract": "We apply transformer language models to protein folding. Attention maps reveal "
                 "contacts. Our model improves accuracy on benchmark datasets.",
     "doi": "https://doi.org/10.1/a", "original_url": "https://example.org/w1.pdf",
     "authors": ["A. One"], "countries": ["PK"], "cited_by": 5, "topics": ["Proteins", "DL"]},
    {"id": "W2", "title": "Protein language models at scale", "year": 2023,
     "abstract": "Scaling protein language models improves folding. Larger transformer models help.",
     "doi": None, "original_url": None, "authors": ["B. Two"], "countries": ["CA"],
     "cited_by": 1, "topics": ["Proteins", "DL"]},
    {"id": "W3", "title": "Quantum error correction with surface codes", "year": 2020,
     "abstract": "Surface codes protect qubits from noise. Thresholds near one percent are observed.",
     "authors": [], "countries": ["PK"], "topics": ["Quantum", "Codes"]},
]


@pytest.fixture
def client(tmp_path, monkeypatch):
    svc = MLService(embedder=HashEmbedder(), store=LocalStore(tmp_path / "v"),
                    cache=SummaryCache(tmp_path / "s.sqlite"))
    svc.index_papers([Paper.from_record(r) for r in V2])
    miner = IncrementalMiner(tmp_path / "p", min_support=0.1, min_baskets=1)
    miner.update([Paper.from_record(r).to_dict() for r in V2], run_date="2026-10-15")
    monkeypatch.setattr(ml_bridge, "get_service", lambda: svc)
    monkeypatch.setattr(ml_bridge, "get_miner", lambda: miner)
    return TestClient(app)


def test_search_filters_and_links(client):
    r = client.get("/api/v1/search", params={"q": "protein folding transformer", "limit": 2}).json()
    assert [x["id"] for x in r["results"]][0] in {"W1", "W2"} and r["results"][0]["score"] > 0
    r = client.get("/api/v1/search", params={"q": "protein", "country": "ca"}).json()
    assert [x["id"] for x in r["results"]] == ["W2"]
    r = client.get("/api/v1/search", params={"q": "protein", "year_from": 2022}).json()
    assert [x["id"] for x in r["results"]] == ["W2"]


def test_paper_detail_summary_and_ask(client):
    d = client.get("/api/v1/papers/W1").json()
    assert d["original_url"] == "https://example.org/w1.pdf"
    assert d["openalex_url"] == "https://openalex.org/W1"
    assert d["summary"] and d["countries"] == ["PK"] and d["authors"] == ["A. One"]
    assert client.get("/api/v1/papers/NOPE").status_code == 404
    hit = client.get("/api/v1/search", params={"q": "protein folding"}).json()["results"]
    assert any(h["one_line_summary"] for h in hit)          # cached summary reused
    a = client.post("/api/v1/papers/W1/ask", json={"question": "What do attention maps reveal?"}).json()
    assert "contacts" in a["answer"] and a["sources"]
    assert client.post("/api/v1/papers/NOPE/ask", json={"question": "x"}).status_code == 404


def test_galaxy_layout(client):
    rows = client.get("/api/v1/galaxy").json()
    assert {r["id"] for r in rows} == {"W1", "W2", "W3"}
    for row in rows:
        assert set(row) == {"id", "x", "y", "z", "cluster_id", "cluster_label", "year"}
        assert isinstance(row["cluster_id"], int) and row["cluster_label"]
        assert isinstance(row["x"], float) and isinstance(row["y"], float) and isinstance(row["z"], float)
    assert {r["id"]: r["year"] for r in rows} == {"W1": 2021, "W2": 2023, "W3": 2020}
    assert client.get("/api/v1/galaxy").json() == rows


def test_related(client):
    r = client.get("/api/v1/papers/W1/related").json()
    assert r[0]["id"] == "W2" and all(x["id"] != "W1" for x in r)
    assert client.get("/api/v1/papers/NOPE/related").status_code == 404


def test_patterns_runs_and_gap_hook(client, monkeypatch):
    p = client.get("/api/v1/patterns").json()
    assert any(x["items"] == ["DL", "Proteins"] for x in p)
    assert all(x["window_start"] == 2021 for x in client.get("/api/v1/patterns", params={"window": 2021}).json())
    monkeypatch.setattr(ml_bridge, "get_gaps", lambda limit=20: [])   # gap handler now implemented
    assert client.get("/api/v1/patterns", params={"trend": "gap"}).status_code == 200
    runs = client.get("/api/v1/runs").json()
    assert runs[0]["id"] == 1 and runs[0]["papers_added"] == 3 and runs[0]["status"] == "success"


def test_patterns_gap(client, monkeypatch):
    from ml.gaps import find_gaps
    tyc = {"QML": {2022: 6, 2023: 12, 2024: 24, 2025: 48},
           "NLP": {2022: 900, 2023: 910, 2024: 905, 2025: 915}}
    monkeypatch.setattr(ml_bridge, "get_gaps",
                        lambda limit=20: find_gaps(tyc, {"QML": [["CA", 2.5]]}, last_year=2025))
    r = client.get("/api/v1/patterns", params={"trend": "gap"})
    assert r.status_code == 200
    body = r.json()
    assert [p["items"] for p in body] == [["QML"]]
    assert body[0]["paper_count"] == 90 and body[0]["top_countries"] == ["CA"]
    assert body[0]["growth_rate"] > 0.5
