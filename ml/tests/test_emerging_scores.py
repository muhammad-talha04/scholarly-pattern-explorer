"""Cluster emerging scores follow galaxy colour, not the rebuild-time cluster id."""
import json
import sqlite3

import numpy as np

from ml.discover import cluster_emerging_scores, refresh_discoveries
from ml.galaxy import with_emerging_scores
from ml.store import LocalStore


def test_scores_are_normalized_and_ignore_unclustered():
    emerging = [
        {"topic_name": "Hot", "topic_id": "h", "growth_score": 0.8},
        {"topic_name": "Warm", "topic_id": "w", "growth_score": 0.4},
    ]
    papers = [
        {"color_index": 3, "topics": ["Hot"]},
        {"color_index": 3, "topics": ["Hot"]},
        {"color_index": 1, "topics": ["Warm", "Other"]},
        {"color_index": 1, "topics": []},
        {"color_index": -1, "topics": ["Hot"]},
    ]
    scores = cluster_emerging_scores(emerging, papers)
    assert scores["3"] == 1.0
    assert scores["1"] == 0.25
    assert "-1" not in scores
    assert all(0.0 <= value <= 1.0 for value in scores.values())


def test_quiet_colours_are_zero_and_topic_id_matches():
    emerging = [{"topic_id": "grow", "topic_name": "Growing Lasers", "growth_score": 1.5}]
    papers = [
        {"color_index": 4, "topics": ["grow"]},
        {"color_index": 2, "topics": ["Flat Graphs"]},
    ]
    scores = cluster_emerging_scores(emerging, papers)
    assert scores == {"4": 1.0, "2": 0.0}


def test_refresh_saves_scores_keyed_by_color(tmp_path, monkeypatch):
    monkeypatch.setenv("ML_DATA_DIR", str(tmp_path / "ml"))
    db = tmp_path / "topic_country_year.sqlite"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE topic_country_year (topic_id TEXT, topic_name TEXT, country_code TEXT, "
                "year INTEGER, paper_count INTEGER, fractional_count REAL)")
    con.execute("CREATE VIEW topic_country_year_v AS SELECT topic_id, topic_name, country_code, "
                "year, paper_count, fractional_count FROM topic_country_year")
    rows = [("grow", "Growing Lasers", "PK", year, n, float(n))
            for year, n in ((2022, 10), (2023, 20), (2024, 40), (2025, 80))]
    con.executemany("INSERT INTO topic_country_year VALUES (?, ?, ?, ?, ?, ?)", rows)
    con.commit()
    con.close()
    store = LocalStore(tmp_path / "v", dim=4)
    vec = np.ones(4, dtype=np.float32)
    store.upsert(["W1", "W2"], np.stack([vec, vec]),
                 [{"topics": ["Growing Lasers"], "title": "a"},
                  {"topics": ["Flat Graphs"], "title": "b"}])
    store.put_document("galaxy", {
        "nodes": [{"id": "W1", "color_index": 5}, {"id": "W2", "color_index": 8}],
        "clusters": [], "links": [],
    })
    refresh_discoveries("2026-10-15", store=store, db_path=db,
                        snapshot_path=tmp_path / "no.json", works_path=tmp_path / "no.jsonl", cs_only=False)
    saved = json.loads((tmp_path / "ml" / "snapshots" / "discoveries-2026-10-15.json").read_text())
    assert saved["emerging_scores"]["5"] == 1.0
    assert saved["emerging_scores"]["8"] == 0.0
    assert "7" not in saved["emerging_scores"]
    latest = json.loads((tmp_path / "ml" / "discoveries.json").read_text())
    assert latest["emerging_scores"] == saved["emerging_scores"]


def test_response_uses_color_index_not_cluster_id():
    graph = {"nodes": [], "links": [], "clusters": [
        {"id": "7", "name": "moved", "label": "moved", "color_index": 1,
         "centroid": {"x": 0, "y": 0, "z": 0}, "size": 2},
    ]}
    # "7" is the current cluster id and must not win over colour 1.
    out = with_emerging_scores(graph, {"1": 0.4, "7": 0.9})
    assert out["clusters"][0]["emerging_score"] == 0.4
    assert out["clusters"][0]["id"] == "7"
    assert graph["clusters"][0].get("emerging_score") is None
