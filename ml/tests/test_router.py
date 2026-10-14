from fastapi.testclient import TestClient

from ml import router as r
from ml.incremental import IncrementalMiner


def test_endpoints(service, tmp_path, monkeypatch):
    miner = IncrementalMiner(tmp_path / "p", min_support=0.1, min_baskets=1)
    miner.update([{"work_id": "A", "pub_year": 2020, "topics": ["x", "y"]}], run_date="2026-10-14")
    monkeypatch.setattr(r, "get_service", lambda: service)
    monkeypatch.setattr(r, "get_miner", lambda: miner)
    c = TestClient(r.app)
    assert c.get("/ml/health").json() == {"ok": True}
    res = c.post("/ml/search", json={"query": "protein folding transformer", "k": 2}).json()
    assert res["results"][0]["work_id"] == "W1"
    assert c.get("/ml/search", params={"q": "qubits"}).status_code == 200
    s = c.get("/ml/papers/W1/summary").json()
    assert s["summary"] and c.get("/ml/papers/W1/summary").json()["cached"] is True
    assert c.get("/ml/papers/NOPE/summary").status_code == 404
    a = c.post("/ml/papers/W1/ask", json={"question": "What do attention maps reveal?"}).json()
    assert "contacts" in a["answer"]
    assert c.get("/ml/patterns", params={"min_k": 2}).json()["patterns"][0]["itemset"] == "x | y"
    assert c.get("/ml/patterns/timeline").json()["timeline"][0]["date"] == "2026-10-14"
