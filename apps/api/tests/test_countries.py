"""Countries and topic-country-year routes read the ingest snapshot."""
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402
from pipeline.country_stats import snapshot, tally  # noqa: E402
import pipeline.country_api as country_api  # noqa: E402

client = TestClient(app)

# Already-normalized work. Kept here so this test does not import pipeline.ingest
# (that module needs requests, which the API job does not install).
BASE = {"id": "W1", "year": 2025, "countries": ["CA", "PK"], "topics": ["AI"],
        "topic_refs": [{"id": "T1", "name": "AI"}]}


def _use(tmp_path, monkeypatch, works):
    p = tmp_path / "snap.json"
    p.write_text(json.dumps(snapshot(tally(works))))
    monkeypatch.setattr(country_api, "SNAPSHOT", p)
    return p


def test_countries_empty_without_snapshot(monkeypatch, tmp_path):
    monkeypatch.setattr(country_api, "SNAPSHOT", tmp_path / "missing.json")
    assert client.get("/api/v1/countries").json() == []
    assert client.get("/api/v1/topic-country-years").json() == []
    assert client.get("/api/v1/countries/PK").status_code == 404


def test_countries_whole_and_fractional(monkeypatch, tmp_path):
    works = [
        BASE,
        {**BASE, "id": "W2", "year": 2026, "countries": ["PK"]},
        {**BASE, "id": "W0", "year": 2024, "countries": []},
    ]
    _use(tmp_path, monkeypatch, works)
    fractional = client.get("/api/v1/countries").json()
    pk = next(r for r in fractional if r["code"] == "PK")
    assert pk["papers"] == 1.5 and pk["fractional_count"] == 1.5 and pk["paper_count"] == 2
    assert pk["counting"] == "fractional"
    assert {y["year"]: y["fractional_count"] for y in pk["by_year"]} == {2025: 0.5, 2026: 1.0}
    full = client.get("/api/v1/countries", params={"counting": "full"}).json()
    pkf = next(r for r in full if r["code"] == "PK")
    assert pkf["papers"] == 2 and pkf["paper_count"] == 2 and pkf["counting"] == "full"
    detail = client.get("/api/v1/countries/pk").json()
    assert detail["fractional_count"] == 1.5
    assert client.get("/api/v1/countries/ZZ").status_code == 404
    pairs = client.get("/api/v1/countries/collaborations").json()
    assert pairs == [{"source": "CA", "target": "PK", "papers": 1.0}]


def test_topic_country_years_endpoint(monkeypatch, tmp_path):
    paper = BASE  # CA + PK, topic T1, year 2025
    _use(tmp_path, monkeypatch, [paper])
    rows = client.get("/api/v1/topic-country-years").json()
    assert len(rows) == 2
    assert abs(sum(r["fractional_count"] for r in rows) - 1) < 1e-9
    assert all(r["paper_count"] == 1 for r in rows)
    assert {r["country_code"] for r in rows} == {"CA", "PK"}
    filtered = client.get("/api/v1/topic-country-years",
                          params={"topic_id": "T1", "country": "pk", "year": 2025}).json()
    assert filtered == [{
        "topic_id": "T1", "topic_name": "AI", "country_code": "PK",
        "year": 2025, "paper_count": 1, "fractional_count": 0.5,
    }]
