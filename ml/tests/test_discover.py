"""Discover precomputes neighbours once. The API looks them up later."""
import numpy as np

from ml.discover import precompute_similar, refresh_discoveries
from ml.store import LocalStore


def _meta(wid, title):
    return {"work_id": wid, "title": title, "pub_year": 2024, "topics": [title],
            "authors": [], "countries": [], "cited_by": 0}


def test_precompute_similar_orders_by_cosine(tmp_path):
    store = LocalStore(tmp_path / "v", dim=4)
    a = np.array([1, 0, 0, 0], dtype=np.float32)
    b = np.array([0.9, 0.1, 0, 0], dtype=np.float32)
    b /= np.linalg.norm(b)
    c = np.array([0, 0, 1, 0], dtype=np.float32)
    store.upsert(["A", "B", "C"], np.stack([a, b, c]),
                 [_meta("A", "Alpha"), _meta("B", "Beta"), _meta("C", "Gamma")])
    neighbours = precompute_similar(store, k=2)
    assert [h["work_id"] for h in neighbours["A"]] == ["B", "C"]
    assert neighbours["A"][0]["score"] > neighbours["A"][1]["score"] >= 0
    assert all(h["work_id"] != "A" for h in neighbours["A"])


def test_refresh_saves_similar_when_the_index_has_papers(tmp_path, monkeypatch):
    monkeypatch.setenv("ML_DATA_DIR", str(tmp_path / "ml"))
    store = LocalStore(tmp_path / "v", dim=4)
    a = np.array([1, 0, 0, 0], dtype=np.float32)
    b = np.array([0.9, 0.1, 0, 0], dtype=np.float32)
    b /= np.linalg.norm(b)
    store.upsert(["A", "B"], np.stack([a, b]), [_meta("A", "Alpha"), _meta("B", "Beta")])
    summary = refresh_discoveries(
        "2026-10-15", store=store, snapshot_path=tmp_path / "no.json",
        db_path=tmp_path / "no.sqlite", works_path=tmp_path / "no.jsonl")
    assert summary["n_similar"] == 2
    from ml.discovery_store import load_discoveries
    saved = load_discoveries()
    assert [h["work_id"] for h in saved["similar"]["A"]] == ["B"]
