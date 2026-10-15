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


def test_related(client):
    r = client.get("/api/v1/papers/W1/related").json()
    assert r[0]["id"] == "W2" and all(x["id"] != "W1" for x in r)
    assert client.get("/api/v1/papers/NOPE/related").status_code == 404


def test_similar(client):
    r = client.get("/api/v1/papers/W1/similar", params={"limit": 1})
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1 and body[0]["id"] == "W2"
    assert body[0]["score"] > 0
    full = client.get("/api/v1/papers/W1/similar").json()
    assert full[0]["id"] == "W2"
    assert all(x["id"] != "W1" for x in full)
    scores = [x["score"] for x in full]
    assert scores == sorted(scores, reverse=True)
    assert client.get("/api/v1/papers/NOPE/similar").status_code == 404


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
    assert "QML" in body[0]["explanation"]


def test_patterns_gap_includes_embedding_gaps(client, monkeypatch):
    monkeypatch.setattr(ml_bridge, "get_gaps", lambda limit=20: [{
        "topic": "QML", "gap_score": 0.2, "growth_rate": 0.3, "paper_count": 40,
        "top_countries": ["CA"], "window_start": 2022, "window_end": 2025}])
    monkeypatch.setattr(ml_bridge, "get_semantic_gaps", lambda limit=10: [{
        "kind": "cooccurrence", "items": ["Alpha", "Beta"], "topic": "Alpha + Beta",
        "gap_score": 0.91, "paper_count": 1, "growth_rate": None,
        "window_start": 2022, "window_end": 2025,
        "explanation": "Alpha and Beta cover closely related subjects. 1 papers study them together.",
        "example_papers": [{"id": "W9", "title": "A bridge paper", "year": 2024}]}])
    body = client.get("/api/v1/patterns", params={"trend": "gap"}).json()
    assert [p["items"] for p in body] == [["Alpha", "Beta"], ["QML"]]
    assert body[0]["support"] == body[0]["gap_score"] == 0.91
    assert body[0]["example_papers"][0]["id"] == "W9"
    assert "Alpha" in body[0]["explanation"]


def test_patterns_emerging_country_filter(client, tmp_path, monkeypatch):
    import sqlite3
    db = tmp_path / "topic_country_year.sqlite"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE topic_country_year (topic_id TEXT, topic_name TEXT, country_code TEXT, "
                "year INTEGER, paper_count INTEGER, fractional_count REAL)")
    con.execute("CREATE VIEW topic_country_year_v AS SELECT topic_id, topic_name, country_code, "
                "year, paper_count, fractional_count FROM topic_country_year")
    rows = []
    for year, n in ((2022, 10), (2023, 20), (2024, 40), (2025, 80)):
        rows.append(("grow", "Growing Lasers", "PK", year, n, float(n)))
    for year in (2022, 2023, 2024, 2025):
        rows.append(("flat", "Flat Graphs", "US", year, 40, 40.0))
    con.executemany("INSERT INTO topic_country_year VALUES (?, ?, ?, ?, ?, ?)", rows)
    con.commit()
    con.close()
    monkeypatch.setenv("TOPIC_COUNTRY_YEAR_DB", str(db))
    monkeypatch.setenv("COUNTRY_SNAPSHOT", str(tmp_path / "missing.json"))
    pk = client.get("/api/v1/patterns", params={"trend": "emerging", "country": "pk"})
    assert pk.status_code == 200
    body = pk.json()
    assert [p["items"] for p in body] == [["Growing Lasers"]]
    assert body[0]["growth_rate"] > 0.5 and body[0]["support"] == body[0]["growth_rate"]
    assert body[0]["paper_count"] == 150
    assert "in PK" in body[0]["explanation"]
    assert client.get("/api/v1/patterns", params={"trend": "emerging", "country": "US"}).json() == []
