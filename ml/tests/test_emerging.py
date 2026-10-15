import json
import sqlite3

import pytest

from ml.emerging import (COLUMNS, combine_rows, load_topic_rows, rank_emerging, rows_from_works)


def _row(topic_id, name, country, year, papers, frac=None):
    return {"topic_id": topic_id, "topic_name": name, "country_code": country, "year": year,
            "paper_count": papers, "fractional_count": papers if frac is None else frac}


def _series(topic_id, name, country, counts, start=2022):
    return [_row(topic_id, name, country, start + i, n) for i, n in enumerate(counts)]


def _ranked(**kw):
    rows = []
    rows += _series("grow", "Growing Lasers", "PK", [10, 20, 40, 80])
    rows += _series("mid", "Modest Sensors", "PK", [20, 22, 24, 26])
    rows += _series("spike", "Spiky Qubits", "PK", [10, 10, 80, 10])
    rows += _series("flat", "Flat Graphs", "PK", [40, 40, 40, 40])
    rows += _series("tiny", "Tiny Ink", "PK", [1, 2, 4, 8])
    rows += _series("drop", "Fading Ink", "PK", [100, 100, 100, 4])
    return rank_emerging(rows, last_year=2025, **kw)


def test_growth_ranking_damps_spikes_and_ignores_noise():
    ranked = _ranked()
    assert [r["topic_name"] for r in ranked] == ["Growing Lasers", "Modest Sensors"]
    top = ranked[0]
    assert top["growth_rate"] > 0.5
    assert top["growth_score"] == top["growth_rate"]
    assert top["paper_count"] == 150
    assert top["window_start"] == 2022 and top["window_end"] == 2025
    assert "Growing Lasers" in top["explanation"]
    assert "Spiky Qubits" not in top["explanation"]


def test_country_filter_uses_that_country_only():
    pk = rank_emerging(
        _series("grow", "Growing Lasers", "PK", [10, 20, 40, 80])
        + _series("grow", "Growing Lasers", "US", [40, 40, 40, 40]),
        country="pk", last_year=2025)
    assert len(pk) == 1
    assert pk[0]["paper_count"] == 150
    assert pk[0]["country"] == "PK"
    assert "in PK" in pk[0]["explanation"]
    us = rank_emerging(
        _series("grow", "Growing Lasers", "PK", [10, 20, 40, 80])
        + _series("grow", "Growing Lasers", "US", [40, 40, 40, 40]),
        country="US", last_year=2025)
    assert us == []


def test_partial_current_year_is_ignored():
    base = _series("grow", "Growing Lasers", "PK", [10, 20, 40, 80])
    extra = base + [_row("grow", "Growing Lasers", "PK", 2026, 5000)]
    a = rank_emerging(base, last_year=2025)[0]["growth_rate"]
    b = rank_emerging(extra, last_year=2025)[0]["growth_rate"]
    assert a == b


def test_rows_from_works_match_table_schema_and_fractional_counts():
    works = [
        {"id": "W1", "year": 2024, "topics": ["Alpha"], "countries": ["ca", "PK", "ca"]},
        {"id": "W2", "year": 2024, "topics": ["Alpha"], "countries": ["CA"]},
        {"id": "W3", "year": 2024, "topics": ["Alpha"], "countries": []},
        {"id": "W4", "year": 2023, "countries": ["DE"],
         "topic_refs": [{"id": "https://openalex.org/T9", "name": "Nice Name"}]},
        {"id": "W5", "year": 2022, "topics": ["Display Only"], "countries": ["FR"],
         "raw": {"topics": [{"id": "https://openalex.org/T7", "display_name": "From Raw"}]}},
    ]
    rows = rows_from_works(works)
    assert rows and all(set(r) == set(COLUMNS) for r in rows)
    alpha = {r["country_code"]: r for r in rows if r["topic_id"] == "Alpha"}
    assert alpha["CA"]["paper_count"] == 2
    assert alpha["PK"]["paper_count"] == 1
    assert alpha["CA"]["fractional_count"] == pytest.approx(1.5)
    assert alpha["PK"]["fractional_count"] == pytest.approx(0.5)
    # W1 and W2 each contribute 1; W3 has no country and is left out.
    assert sum(r["fractional_count"] for r in rows if r["topic_id"] == "Alpha") == pytest.approx(2)
    nice = next(r for r in rows if r["topic_id"] == "T9")
    assert nice["topic_name"] == "Nice Name" and nice["country_code"] == "DE"
    raw = next(r for r in rows if r["topic_id"] == "T7")
    assert raw["topic_name"] == "From Raw"


def test_combine_rows_matches_full_count():
    batch1 = [
        {"id": "W1", "year": 2024, "topics": ["Alpha"], "countries": ["CA", "PK"]},
        {"id": "W2", "year": 2025, "topics": ["Beta"], "countries": ["US"]},
    ]
    batch2 = [
        {"id": "W3", "year": 2024, "topics": ["Alpha"], "countries": ["CA"]},
    ]
    combined = combine_rows(rows_from_works(batch1), rows_from_works(batch2))
    full = rows_from_works(batch1 + batch2)
    assert [(r["topic_id"], r["country_code"], r["year"], r["paper_count"]) for r in combined] == [
        (r["topic_id"], r["country_code"], r["year"], r["paper_count"]) for r in full]
    for got, exp in zip(combined, full):
        assert got["fractional_count"] == pytest.approx(exp["fractional_count"])


def _write_table(path, rows):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE topic_country_year (topic_id TEXT NOT NULL, topic_name TEXT NOT NULL, "
                "country_code TEXT NOT NULL, year INTEGER NOT NULL, paper_count INTEGER NOT NULL, "
                "fractional_count REAL NOT NULL, PRIMARY KEY (topic_id, country_code, year))")
    con.execute("CREATE VIEW topic_country_year_v AS SELECT topic_id, topic_name, country_code, "
                "year, paper_count, fractional_count FROM topic_country_year")
    con.executemany("INSERT INTO topic_country_year VALUES (?, ?, ?, ?, ?, ?)",
                    [tuple(r[c] for c in COLUMNS) for r in rows])
    con.commit()
    con.close()


def test_loader_prefers_table_then_snapshot_then_works(tmp_path):
    table_rows = _series("T1", "From Table", "PK", [10, 20, 40, 80])
    db = tmp_path / "topic_country_year.sqlite"
    _write_table(db, table_rows)
    snap = tmp_path / "snap.json"
    snap.write_text(json.dumps({"topic_country_year": _series("S1", "From Snapshot", "CA", [5, 5, 5, 5])}))
    works = tmp_path / "works_v2.jsonl"
    works.write_text(json.dumps({"id": "W1", "year": 2024, "topics": ["From Works"], "countries": ["US"]}) + "\n")

    rows, src = load_topic_rows(snap, db, works)
    assert src == "table" and {r["topic_name"] for r in rows} == {"From Table"}

    empty = tmp_path / "empty.sqlite"
    con = sqlite3.connect(empty)
    con.execute("CREATE TABLE topic_country_year (topic_id TEXT, topic_name TEXT, country_code TEXT, "
                "year INTEGER, paper_count INTEGER, fractional_count REAL)")
    con.commit()
    con.close()
    rows, src = load_topic_rows(snap, empty, works)
    assert src == "snapshot" and rows[0]["topic_name"] == "From Snapshot"

    plain = tmp_path / "plain.json"
    plain.write_text(json.dumps({"countries": []}))
    rows, src = load_topic_rows(plain, tmp_path / "missing.sqlite", works)
    assert src == "works" and rows[0]["topic_id"] == "From Works"

    bad = tmp_path / "bad.sqlite"
    bad.write_text("not a database")
    rows, src = load_topic_rows(snap, bad, works)
    assert src == "snapshot"


def test_refresh_snapshot_uses_table_without_rebuilding_vectors(tmp_path, monkeypatch):
    monkeypatch.setenv("ML_DATA_DIR", str(tmp_path / "ml"))
    db = tmp_path / "topic_country_year.sqlite"
    _write_table(db, _series("grow", "Growing Lasers", "PK", [10, 20, 40, 80]))
    from ml.discover import refresh_discoveries
    from ml.store import LocalStore
    summary = refresh_discoveries(
        "2026-10-15", store=LocalStore(tmp_path / "v"), db_path=db,
        snapshot_path=tmp_path / "no.json", works_path=tmp_path / "no.jsonl")
    assert summary["topic_source"] == "table"
    assert summary["n_emerging"] == 1 and summary["n_semantic_gaps"] == 0
    saved = json.loads((tmp_path / "ml" / "snapshots" / "discoveries-2026-10-15.json").read_text())
    assert saved["emerging"][0]["topic_name"] == "Growing Lasers"


def test_default_loader_reads_postgres_when_selected(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/db")
    monkeypatch.setenv("ML_VECTOR_BACKEND", "pgvector")
    row = {"topic_id": "T1", "topic_name": "From Postgres", "country_code": "PK",
           "year": 2024, "paper_count": 4, "fractional_count": 4.0}
    monkeypatch.setattr("pipeline.aggregate_store.read_topic_country_year", lambda conn=None: [row])
    rows, src = load_topic_rows()
    assert src == "table" and rows[0]["topic_name"] == "From Postgres"


def test_explicit_sqlite_path_skips_postgres(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/db")
    monkeypatch.setenv("ML_VECTOR_BACKEND", "pgvector")

    def boom(conn=None):
        raise AssertionError("postgres")

    monkeypatch.setattr("pipeline.aggregate_store.read_topic_country_year", boom)
    rows, src = load_topic_rows(tmp_path / "no.json", tmp_path / "missing.sqlite", tmp_path / "no.jsonl")
    assert src == "none" and rows == []


def test_empty_postgres_falls_through_to_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/db")
    monkeypatch.setenv("ML_VECTOR_BACKEND", "pgvector")
    monkeypatch.setenv("TOPIC_COUNTRY_YEAR_DB", str(tmp_path / "missing.sqlite"))
    monkeypatch.setenv("COUNTRY_SNAPSHOT", str(tmp_path / "snap.json"))
    monkeypatch.setenv("ML_WORKS_PATH", str(tmp_path / "no.jsonl"))
    snap = tmp_path / "snap.json"
    snap.write_text(json.dumps({"topic_country_year": _series("S1", "From Snapshot", "CA", [5, 5, 5, 5])}))
    monkeypatch.setattr("pipeline.aggregate_store.read_topic_country_year", lambda conn=None: [])
    rows, src = load_topic_rows()
    assert src == "snapshot" and rows[0]["topic_name"] == "From Snapshot"


def test_string_years_from_snapshot_json(tmp_path):
    snap = tmp_path / "snap.json"
    payload = [_row("grow", "Growing Lasers", "PK", y, n) for y, n in
               zip((2022, 2023, 2024, 2025), (10, 20, 40, 80))]
    for row in payload:
        row["year"] = str(row["year"])
    snap.write_text(json.dumps({"topic_country_year": payload}))
    rows, src = load_topic_rows(snap, tmp_path / "missing.sqlite", tmp_path / "missing.jsonl")
    assert src == "snapshot"
    assert rank_emerging(rows, last_year=2025)[0]["topic_name"] == "Growing Lasers"
