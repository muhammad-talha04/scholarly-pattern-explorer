import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from pipeline import country_api

SNAP = {
    "countries": [{"code": "PK", "name": "Pakistan", "papers": 1.5, "growth_pct": 10.0,
                   "top_topics": ["AI"], "counting": "fractional"},
                  {"code": "CA", "name": "Canada", "papers": 0.5, "growth_pct": None,
                   "top_topics": [], "counting": "fractional"}],
    "countries_full": [{"code": "PK", "name": "Pakistan", "papers": 2, "growth_pct": 10.0,
                        "top_topics": ["AI"], "counting": "full"},
                       {"code": "CA", "name": "Canada", "papers": 1, "growth_pct": None,
                        "top_topics": [], "counting": "full"}],
    "collaborations": [{"source": "CA", "target": "PK", "papers": 1}],
}


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


def test_collaborations(client):
    r = client.get("/api/v1/countries/collaborations", params={"counting": "full"}).json()
    assert r == [{"source": "CA", "target": "PK", "papers": 1.0}]


def test_no_snapshot_is_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(country_api, "SNAPSHOT", tmp_path / "missing.json")
    c = TestClient(app)
    assert c.get("/api/v1/countries").json() == []
    assert c.get("/api/v1/countries/collaborations").json() == []
