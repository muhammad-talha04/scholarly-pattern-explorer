from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/api/v1/health").json() == {"status": "ok"}


def test_search_shape():
    r = client.get("/api/v1/search", params={"q": "graph neural networks"})
    assert r.status_code == 200
    assert r.json() == {"query": "graph neural networks", "results": []}


def test_all_contract_routes_exist():
    paths = set(app.openapi()["paths"])
    for p in ["/search", "/papers/{paper_id}", "/papers/{paper_id}/ask",
              "/papers/{paper_id}/related", "/patterns", "/countries",
              "/countries/{code}", "/runs", "/galaxy"]:
        assert "/api/v1" + p in paths
