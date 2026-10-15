"""Country routes: counting modes from #2/#4, plus whole/fractional and topic-country-year."""
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from pipeline import country_api
from pipeline.country_stats import snapshot, tally

SNAP = {
    "countries": [{"code": "PK", "name": "Pakistan", "papers": 1.5, "growth_pct": 10.0,
                   "top_topics": ["AI"], "counting": "fractional"},
                  {"code": "CA", "name": "Canada", "papers": 0.5, "growth_pct": None,
                   "top_topics": [], "counting": "fractional"}],
    "countries_full": [{"code": "PK", "name": "Pakistan", "papers": 2, "growth_pct": 10.0,
                        "top_topics": ["AI"], "counting": "full"},
                       {"code": "CA", "name": "Canada", "papers": 1, "growth_pct": None,
                        "top_topics": [], "counting": "full"}],
    "collaborations": [{"source": "CA", "target": "PK", "papers": 0.25}],
    "collaborations_1n": [{"source": "CA", "target": "PK", "papers": 0.5}],
    "collaborations_full": [{"source": "CA", "target": "PK", "papers": 1}],
}

# Already-normalized work. Kept here so this test does not import pipeline.ingest
# (that module needs requests, which the API job does not install).
BASE = {"id": "W1", "year": 2025, "countries": ["CA", "PK"], "topics": ["AI"],
        "topic_refs": [{"id": "T1", "name": "AI"}]}


@pytest.fixture
def client(tmp_path, monkeypatch):
    f = tmp_path / "snap.json"
    f.write_text(json.dumps(SNAP))
    monkeypatch.setattr(country_api, "SNAPSHOT", f)
    return TestClient(app)


def test_countries_fractional_default_and_full(client):
    r = client.get("/api/v1/countries").json()
    assert r[0]["papers"] == 1.5 and r[0]["counting"] == "fractional"
    r = client.get("/api/v1/countries", params={"counting": "full"}).json()
    assert r[0]["papers"] == 2 and r[0]["counting"] == "full"
    assert client.get("/api/v1/countries", params={"counting": "bogus"}).status_code == 422


def test_country_detail(client):
    assert client.get("/api/v1/countries/pk").json()["papers"] == 1.5
    assert client.get("/api/v1/countries/PK", params={"counting": "full"}).json()["papers"] == 2
    assert client.get("/api/v1/countries/ZZ").status_code == 404


@pytest.mark.parametrize("counting,papers", [(None, 0.25), ("fractional", 0.25),
                                             ("per_country", 0.5), ("full", 1.0)])
def test_collaborations_all_counting_modes(client, counting, papers):
    params = {"counting": counting} if counting else {}
    r = client.get("/api/v1/countries/collaborations", params=params).json()
    assert r == [{"source": "CA", "target": "PK", "papers": papers}]


@pytest.mark.parametrize("counting", ["fractional", "per_country", "full"])
def test_countries_accept_all_counting_modes(client, counting):
    assert client.get("/api/v1/countries", params={"counting": counting}).status_code == 200
    assert client.get("/api/v1/countries/PK", params={"counting": counting}).status_code == 200


def test_no_snapshot_is_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(country_api, "SNAPSHOT", tmp_path / "missing.json")
    c = TestClient(app)
    assert c.get("/api/v1/countries").json() == []
    assert c.get("/api/v1/countries/collaborations").json() == []
    assert c.get("/api/v1/topic-country-years").json() == []


def _use(tmp_path, monkeypatch, works):
    p = tmp_path / "snap.json"
    p.write_text(json.dumps(snapshot(tally(works))))
    monkeypatch.setattr(country_api, "SNAPSHOT", p)
    return TestClient(app)


def test_countries_whole_and_fractional(monkeypatch, tmp_path):
    works = [
        BASE,
        {**BASE, "id": "W2", "year": 2026, "countries": ["PK"]},
        {**BASE, "id": "W0", "year": 2024, "countries": []},
    ]
    client = _use(tmp_path, monkeypatch, works)
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
    client = _use(tmp_path, monkeypatch, [BASE])
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
