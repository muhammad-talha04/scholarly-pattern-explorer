import json

import pytest
from fastapi.testclient import TestClient

from app import aggregates, ml_bridge
from app.main import app
from pipeline import country_api
from ml.store import LocalStore, aggregate_meta


class _Svc:
    def __init__(self, store):
        self.store = store


META = [
    {"publication_date": "2025-01-10", "pub_year": 2025, "topics": ["LLM", "Vision"]},
    {"publication_date": "2025-01-20", "topics": ["LLM"]},
    {"publication_date": "2025-03-02", "topics": ["Quantum"]},
    {"publication_date": None, "pub_year": 2024, "topics": ["LLM"]},       # year only
    {"created": "2023-06-01", "topics": []},                                # created fallback
    {"title": "no date"},                                                   # dropped
]


@pytest.fixture
def client(tmp_path, monkeypatch):
    store = LocalStore(tmp_path / "v")
    store.ids = [f"W{i}" for i in range(len(META))]
    store.meta = dict(zip(store.ids, META))
    store._rates = {}
    store.path = None
    store.put_sampling_rate("2025-01", 1000, 2, "f")
    store.put_sampling_rate("2025-03", 500, 1, "f")
    calls = {"n": 0}
    real = store.aggregate_counts

    def counted():
        calls["n"] += 1
        return real()
    store.aggregate_counts = counted
    monkeypatch.setattr(ml_bridge, "get_service", lambda: _Svc(store))
    aggregates.clear_cache()
    c = TestClient(app)
    c.calls = calls
    yield c
    aggregates.clear_cache()


def test_year_month_fallback():
    out = aggregate_meta(META)["papers"]
    assert out == {(2025, "2025-01"): 2, (2025, "2025-03"): 1, (2024, None): 1, (2023, "2023-06"): 1}


def test_publications_year(client):
    r = client.get("/api/v1/aggregates/publications").json()
    assert r["grain"] == "year" and r["year"] is None and r["total"] == 5
    assert [(b["key"], b["paper_count"], b["sampled"]) for b in r["buckets"]] == [
        ("2023", 1, 1), ("2024", 1, 1), ("2025", 3, 3)]
    by = {b["key"]: b["estimated_total"] for b in r["buckets"]}
    assert by == {"2023": None, "2024": None, "2025": 1500}


def test_publications_month_fills_all_twelve(client):
    r = client.get("/api/v1/aggregates/publications", params={"grain": "month", "year": 2025}).json()
    assert r["year"] == 2025 and len(r["buckets"]) == 12 and r["total"] == 3
    jan, feb, mar = r["buckets"][:3]
    assert (jan["key"], jan["paper_count"], jan["estimated_total"]) == ("2025-01", 2, 1000)
    assert (feb["paper_count"], feb["estimated_total"]) == (0, None)
    assert (mar["paper_count"], mar["estimated_total"]) == (1, 500)
    assert client.get("/api/v1/aggregates/publications", params={"grain": "month"}).status_code == 422
    assert client.get("/api/v1/aggregates/publications", params={"grain": "day"}).status_code == 422


def test_topics_top_and_other(client):
    r = client.get("/api/v1/aggregates/topics", params={"grain": "month", "year": 2025, "top": 1}).json()
    assert r["top"] == 1 and [s["name"] for s in r["series"]] == ["LLM", "Other"]
    llm, other = r["series"]
    assert len(llm["points"]) == 12 and llm["points"][0] == {"key": "2025-01", "value": 1.5}
    assert other["points"][0]["value"] == 0.5 and other["points"][2]["value"] == 1.0
    assert r["period"][0] == {"key": "2025-01", "sampled": 2, "estimated_total": 1000}
    yr = client.get("/api/v1/aggregates/topics").json()
    assert [p["key"] for p in yr["series"][0]["points"]] == ["2023", "2024", "2025"]
    assert client.get("/api/v1/aggregates/topics", params={"top": 0}).status_code == 422


def test_cache_ttl(client, monkeypatch):
    client.get("/api/v1/aggregates/publications")
    client.get("/api/v1/aggregates/topics")
    assert client.calls["n"] == 1
    monkeypatch.setenv("AGGREGATES_TTL_SECONDS", "0")
    monkeypatch.setenv("AGGREGATES_SYNC_REFRESH", "1")
    client.get("/api/v1/aggregates/publications")
    assert client.calls["n"] == 2


def test_countries_top_other_and_year(client, tmp_path, monkeypatch):
    rows = [{"code": c, "name": c, "papers": p, "top_topics": [], "counting": "fractional"}
            for c, p in [("CN", 5.0), ("US", 3.0), ("PK", 1.0), ("CA", 0.5)]]
    tally = {"by_year": {r["code"]: {"2025": int(r["papers"] * 2)} for r in rows},
             "frac": {r["code"]: {"2025": r["papers"]} for r in rows}}
    f = tmp_path / "snap.json"
    f.write_text(json.dumps({"countries": rows, "countries_full": rows, "tally": tally}))
    monkeypatch.setattr(country_api, "SNAPSHOT", f)
    r = client.get("/api/v1/aggregates/countries", params={"top": 2}).json()
    assert [i["code"] for i in r["items"]] == ["CN", "US"] and r["total"] == 5
    assert r["other"] == {"papers": 1.5, "countries": 2}
    r = client.get("/api/v1/aggregates/countries", params={"top": 12, "year": 2025, "counting": "full"}).json()
    assert r["other"] is None and r["items"][0] == {"code": "CN", "name": "CN", "papers": 10.0}
    assert r["total"] == 3 and r["period"] == [{"key": "2025", "sampled": 3, "estimated_total": 1500}]


def test_stale_read_serves_cache_and_refreshes_in_background(client, monkeypatch):
    client.get("/api/v1/aggregates/publications")
    monkeypatch.setenv("AGGREGATES_TTL_SECONDS", "0")
    started = []
    monkeypatch.setattr(aggregates.threading, "Thread",
                        lambda target, daemon: type("T", (), {"start": lambda self: started.append(target)})())
    r = client.get("/api/v1/aggregates/publications").json()
    assert r["total"] == 5 and client.calls["n"] == 1 and len(started) == 1
    started[0]()          # the background rescan
    assert client.calls["n"] == 2 and not aggregates._refreshing.locked()
