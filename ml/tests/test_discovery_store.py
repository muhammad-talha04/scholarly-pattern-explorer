"""Discoveries are a local file, or rows in discovery_snapshots when Postgres is on."""
import json

from ml.discovery_store import load_discoveries, save_discoveries


class _Cursor:
    def __init__(self, conn):
        self.conn = conn
        self._rows = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        text = " ".join(sql.split())
        self.conn.sql.append(text)
        if text.lower().startswith("insert"):
            run_date, kind, country, results, created_at = params
            self.conn.rows.append({
                "run_date": run_date, "kind": kind, "country_code": country,
                "results": json.loads(results), "created_at": created_at,
            })
        elif text.lower().startswith("select"):
            if not self.conn.rows:
                self._rows = []
                return
            latest = max(row["created_at"] for row in self.conn.rows)
            self._rows = [
                (row["kind"], row["country_code"], row["results"], str(row["run_date"]))
                for row in self.conn.rows if row["created_at"] == latest
            ]

    def fetchall(self):
        return self._rows


class _Conn:
    def __init__(self):
        self.rows = []
        self.sql = []

    def cursor(self):
        return _Cursor(self)


def test_save_and_load_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("ML_DATA_DIR", str(tmp_path / "ml"))
    payload = {
        "date": "2026-10-15",
        "gaps": [{"gap_score": 0.91, "example_papers": None, "items": ["Alpha", "Beta"]}],
        "emerging": [],
        "emerging_by_country": {"PK": [{"topic_name": "Growing Lasers"}]},
    }
    path = save_discoveries(payload)
    assert path == tmp_path / "ml" / "discoveries.json"
    assert load_discoveries() == payload
    dated = tmp_path / "ml" / "snapshots" / "discoveries-2026-10-15.json"
    assert json.loads(dated.read_text())["gaps"][0]["gap_score"] == 0.91
    assert json.loads(dated.read_text())["gaps"][0]["example_papers"] is None


def test_load_missing_or_corrupt_is_none(tmp_path, monkeypatch):
    monkeypatch.setenv("DISCOVERIES_PATH", str(tmp_path / "missing.json"))
    assert load_discoveries() is None
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    assert load_discoveries(bad) is None
    bad.write_text("[]", encoding="utf-8")
    assert load_discoveries(bad) is None


def test_load_reads_the_latest_file_not_the_dated_copy(tmp_path):
    path = tmp_path / "discoveries.json"
    save_discoveries({"date": "2026-10-01", "gaps": [{"gap_score": 0.1}]}, path)
    save_discoveries({"date": "2026-10-15", "gaps": [{"gap_score": 0.91}]}, path)
    assert load_discoveries(path)["date"] == "2026-10-15"
    assert load_discoveries(path)["gaps"][0]["gap_score"] == 0.91
    assert (tmp_path / "snapshots" / "discoveries-2026-10-01.json").is_file()


def _use_postgres(monkeypatch, conn):
    monkeypatch.setenv("ML_VECTOR_BACKEND", "pgvector")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/scholarly")
    monkeypatch.setattr("ml.discovery_store._connection", lambda: conn)


def test_database_rows_match_discovery_snapshots_columns(tmp_path, monkeypatch):
    monkeypatch.delenv("DISCOVERIES_PATH", raising=False)
    monkeypatch.setenv("ML_DATA_DIR", str(tmp_path / "ml"))
    conn = _Conn()
    _use_postgres(monkeypatch, conn)
    payload = {
        "date": "2026-10-15",
        "topic_source": "table",
        "n_emerging": 1,
        "n_semantic_gaps": 0,
        "gaps": [{"gap_score": 0.91, "example_papers": None, "items": ["Alpha", "Beta"]}],
        "emerging": [{"topic_name": "Growing Lasers", "growth_score": 0.8}],
        "emerging_by_country": {"pk": [{"topic_name": "Growing Lasers", "growth_score": 0.7}]},
        "semantic_gaps": [],
        "similar": {"W1": [{"work_id": "W2", "score": 0.9}]},
    }
    save_discoveries(payload)
    inserts = [sql for sql in conn.sql if sql.lower().startswith("insert")]
    assert inserts
    assert inserts[0] == (
        "INSERT INTO discovery_snapshots (run_date, kind, country_code, results, created_at) "
        "VALUES (%s, %s, %s, %s::jsonb, %s)"
    )
    assert all(" id" not in sql.lower() for sql in inserts)
    stored = {(row["kind"], row["country_code"]) for row in conn.rows}
    assert stored == {
        ("gap", None), ("emerging", None), ("emerging", "PK"),
        ("semantic_gaps", None), ("similar", None), ("run", None),
    }
    # The release file is written too, then overwritten. The read still uses the table.
    discoveries = tmp_path / "ml" / "discoveries.json"
    assert discoveries.is_file()
    discoveries.write_text(json.dumps({"date": "1999-01-01", "gaps": [{"gap_score": 0.1}]}), encoding="utf-8")
    loaded = load_discoveries()
    assert any(sql.startswith(
        "SELECT kind, country_code, results, run_date::text FROM discovery_snapshots") for sql in conn.sql)
    assert loaded["date"] == "2026-10-15"
    assert loaded["topic_source"] == "table"
    assert loaded["gaps"][0]["gap_score"] == 0.91
    assert loaded["gaps"][0]["example_papers"] is None
    assert loaded["emerging"][0]["topic_name"] == "Growing Lasers"
    assert loaded["emerging_by_country"]["PK"][0]["growth_score"] == 0.7
    assert loaded["similar"]["W1"][0]["work_id"] == "W2"
    assert "semantic_gaps" in loaded

    save_discoveries({
        "date": "2026-10-16",
        "gaps": [{"gap_score": 0.2}],
        "emerging": [],
        "emerging_by_country": {},
    })
    assert load_discoveries()["date"] == "2026-10-16"
    assert load_discoveries()["gaps"][0]["gap_score"] == 0.2
    assert "similar" not in load_discoveries()
    assert any(row["run_date"] == "2026-10-15" for row in conn.rows)


def test_local_backend_ignores_database_url(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/scholarly")
    monkeypatch.setenv("ML_VECTOR_BACKEND", "local")
    monkeypatch.delenv("DISCOVERIES_PATH", raising=False)
    monkeypatch.setenv("ML_DATA_DIR", str(tmp_path / "ml"))

    def boom():
        raise AssertionError("local backend opened Postgres")

    monkeypatch.setattr("ml.discovery_store._connection", boom)
    save_discoveries({"date": "2026-10-15", "gaps": [{"gap_score": 0.91}], "emerging": []})
    assert load_discoveries()["gaps"][0]["gap_score"] == 0.91
    assert (tmp_path / "ml" / "discoveries.json").is_file()


def test_explicit_path_stays_a_file_when_postgres_is_configured(tmp_path, monkeypatch):
    _use_postgres(monkeypatch, _Conn())

    def boom():
        raise AssertionError("explicit path opened Postgres")

    monkeypatch.setattr("ml.discovery_store._connection", boom)
    path = tmp_path / "snap.json"
    save_discoveries({"date": "2026-10-15", "gaps": [{"gap_score": 0.91}]}, path)
    assert load_discoveries(path)["gaps"][0]["gap_score"] == 0.91
