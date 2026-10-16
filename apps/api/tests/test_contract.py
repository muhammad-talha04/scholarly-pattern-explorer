from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/api/v1/health").json() == {"status": "ok"}


def test_search_shape():
    r = client.get("/api/v1/search", params={"q": "graph neural networks"})
    assert r.status_code == 200
    assert r.json() == {"query": "graph neural networks", "results": [], "total": 0, "limit": 20, "offset": 0}


def test_all_contract_routes_exist():
    paths = set(app.openapi()["paths"])
    for p in ["/search", "/papers/{paper_id}", "/papers/{paper_id}/ask",
              "/papers/{paper_id}/related", "/papers/{paper_id}/similar", "/patterns",
              "/countries", "/countries/{code}", "/topic-country-years", "/runs", "/galaxy", "/stats"]:
        assert "/api/v1" + p in paths


def test_search_sends_server_timing():
    r = client.get("/api/v1/search", params={"q": "graph"})
    assert "total;dur=" in r.headers["server-timing"]
