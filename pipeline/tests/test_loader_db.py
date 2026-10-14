"""Integration test: applies db/migrations and upserts a record twice.

Runs only when DATABASE_URL points at an empty pgvector Postgres (CI service).
"""
import os
from pathlib import Path

import pytest

from spe_pipeline.loader import load
from spe_pipeline.parse import parse_work

from .test_parse_windows import REC

DSN = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="DATABASE_URL not set")
MIGRATION = Path(__file__).resolve().parents[2] / "db" / "migrations" / "0001_init.sql"


def test_migrate_and_upsert_idempotent():
    import psycopg

    with psycopg.connect(DSN) as conn:
        conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        conn.execute(MIGRATION.read_text())
        conn.commit()
        assert load(conn, [parse_work(REC)]) == {2021}
        assert load(conn, [parse_work(REC)]) == {2021}
        n = conn.execute("SELECT count(*) FROM work_topics").fetchone()[0]
        c = conn.execute("SELECT count(*) FROM work_countries").fetchone()[0]
        hit = conn.execute(
            "SELECT work_id FROM works WHERE tsv @@ plainto_tsquery('english','hello')"
        ).fetchone()
        assert (n, c, hit[0]) == (2, 3, "W1")
