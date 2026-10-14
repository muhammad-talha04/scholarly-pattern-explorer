from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_placeholders():
    for path in ["/search?q=x", "/papers/W1", "/papers/W1/summary", "/patterns",
                 "/patterns/lifecycles", "/countries", "/timeline"]:
        r = client.get(path)
        assert r.status_code == 200, path
        assert r.json()["status"] == "not_implemented"
    assert client.post("/papers/W1/chat", json={"message": "hi"}).status_code == 200
    assert client.get("/search").status_code == 422
