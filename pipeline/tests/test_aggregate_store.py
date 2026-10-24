"""Topic-country-year reads and writes follow the shared store.

Postgres is mocked. Nothing here opens a real database, so CI needs no DATABASE_URL.
"""
import json
from pathlib import Path

import pytest

from pipeline.aggregate_store import (
    COLUMNS,
    read_topic_country_year,
    replace_topic_country_year,
    use_postgres,
)
from pipeline.country_stats import TOPIC_COUNTRY_YEAR_COLUMNS

ROOT = Path(__file__).resolve().parents[2]


class _Cursor:
    def __init__(self, mem):
        self.mem = mem
        self._result = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.mem.log.append(sql)
        text = " ".join(sql.split()).upper()
        if text.startswith("DELETE"):
            self.mem.rows.clear()
        elif text.startswith("SELECT"):
            self._result = list(self.mem.rows)

    def executemany(self, sql, seq):
        self.mem.log.append(sql)
        for params in seq:
            self.mem.rows.append(tuple(params))

    def fetchall(self):
        return list(self._result)


class Memory:
    """In-memory stand-in for a psycopg connection. No network."""

    def __init__(self):
        self.rows = []
        self.log = []

    def cursor(self):
        return _Cursor(self)

    def commit(self):
        self.log.append("commit")

    def rollback(self):
        self.log.append("rollback")

    def close(self):
        self.log.append("close")


def _row(topic_id, country, year, papers, frac, name="Name"):
    return {
        "topic_id": topic_id,
        "topic_name": name,
        "country_code": country,
        "year": year,
        "paper_count": papers,
        "fractional_count": frac,
    }


def test_migration_columns_match_the_writer():
    sql = (ROOT / "db" / "migrations" / "002_topic_country_year.sql").read_text(encoding="utf-8")
    assert list(COLUMNS) == list(TOPIC_COUNTRY_YEAR_COLUMNS)
    for col in COLUMNS:
        assert col in sql
    assert "PRIMARY KEY (topic_id, country_code, year)" in sql
    assert "CREATE OR REPLACE VIEW topic_country_year_v" in sql
    assert "SELECT topic_id, topic_name, country_code, year, paper_count, fractional_count" in sql
    assert "security_invoker" in sql


def test_use_postgres_follows_the_store_rule(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("ML_VECTOR_BACKEND", raising=False)
    assert use_postgres() is False

    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/db")
    assert use_postgres() is True

    monkeypatch.setenv("ML_VECTOR_BACKEND", "local")
    assert use_postgres() is False

    monkeypatch.setenv("ML_VECTOR_BACKEND", "pgvector")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert use_postgres() is True


def test_replace_does_not_add_onto_existing_rows():
    mem = Memory()
    replace_topic_country_year([_row("A", "PK", 2024, 1, 1.0, "Alpha")], conn=mem)
    replace_topic_country_year([
        _row("A", "PK", 2024, 1, 1.0, "Alpha"),
        _row("B", "CA", 2024, 1, 0.5, "Beta"),
    ], conn=mem)
    got = {(r["topic_id"], r["country_code"]): r["paper_count"]
           for r in read_topic_country_year(conn=mem)}
    assert got == {("A", "PK"): 1, ("B", "CA"): 1}
    assert not any("DROP" in sql.upper() for sql in mem.log)
    assert any("DELETE FROM topic_country_year" in sql for sql in mem.log)


def test_replace_requires_database_url_when_it_opens_a_connection(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        replace_topic_country_year([_row("A", "PK", 2024, 1, 1.0)])


def _work(wid, year, countries, topic_id, name):
    return {
        "id": wid, "year": year, "countries": countries, "topics": [name],
        "topic_refs": [{"id": topic_id, "name": name}],
    }


def test_country_stats_replaces_postgres_incrementally(tmp_path, monkeypatch):
    import pipeline.country_stats as cs

    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/db")
    monkeypatch.delenv("ML_VECTOR_BACKEND", raising=False)
    mem = Memory()
    monkeypatch.setattr("pipeline.aggregate_store._connect", lambda migrate=False: mem)

    first = _work("W1", 2024, ["PK"], "T1", "AI")
    second = _work("W2", 2024, ["PK", "CA"], "T9", "Graphs")
    new1, new2 = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    out = tmp_path / "snap.json"
    new1.write_text(json.dumps(first) + "\n")
    new2.write_text(json.dumps(second) + "\n")
    cs.main(["--new", str(new1), "--out", str(out)])
    cs.main(["--new", str(new2), "--prev", str(out), "--out", str(out)])

    stored = {(r["topic_id"], r["country_code"], r["year"]): (r["paper_count"], r["fractional_count"])
              for r in read_topic_country_year(conn=mem)}
    assert stored[("T1", "PK", 2024)] == (1, 1.0)
    assert stored[("T9", "PK", 2024)][0] == 1 and stored[("T9", "CA", 2024)][0] == 1
    assert abs(stored[("T9", "PK", 2024)][1] + stored[("T9", "CA", 2024)][1] - 1) < 1e-9
    assert not (tmp_path / "topic_country_year.sqlite").exists()
    assert "postgresql://example.invalid/db" not in (ROOT / "pipeline" / "aggregate_store.py").read_text()


def test_explicit_table_stays_sqlite_when_database_url_is_set(tmp_path, monkeypatch):
    import sqlite3
    import pipeline.country_stats as cs

    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/db")
    monkeypatch.delenv("ML_VECTOR_BACKEND", raising=False)

    def boom(migrate=False):
        raise AssertionError("postgres")

    monkeypatch.setattr("pipeline.aggregate_store._connect", boom)
    work = _work("W1", 2024, ["PK"], "T1", "AI")
    new = tmp_path / "a.jsonl"
    out, table = tmp_path / "snap.json", tmp_path / "t.sqlite"
    new.write_text(json.dumps(work) + "\n")
    cs.main(["--new", str(new), "--out", str(out), "--table", str(table)])
    con = sqlite3.connect(table)
    cols = [r[1] for r in con.execute("PRAGMA table_info(topic_country_year)")]
    assert cols == list(TOPIC_COUNTRY_YEAR_COLUMNS)
    assert con.execute("SELECT paper_count FROM topic_country_year").fetchone()[0] == 1


def test_local_backend_keeps_sqlite_beside_the_snapshot(tmp_path, monkeypatch):
    import pipeline.country_stats as cs

    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/db")
    monkeypatch.setenv("ML_VECTOR_BACKEND", "local")
    monkeypatch.delenv("TOPIC_COUNTRY_YEAR_DB", raising=False)

    def boom(migrate=False):
        raise AssertionError("postgres")

    monkeypatch.setattr("pipeline.aggregate_store._connect", boom)
    work = _work("W1", 2024, ["CA"], "T1", "AI")
    new, out = tmp_path / "a.jsonl", tmp_path / "snap.json"
    new.write_text(json.dumps(work) + "\n")
    cs.main(["--new", str(new), "--out", str(out)])
    assert (tmp_path / "topic_country_year.sqlite").is_file()
