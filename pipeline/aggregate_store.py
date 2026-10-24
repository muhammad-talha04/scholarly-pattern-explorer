"""Topic × country × year table on the shared storage backend.

Postgres (the ``topic_country_year`` table from ``db/migrations/002``) when
``ml.paths.use_postgres()`` is true — the same rule as ``ml.store.get_store``.
The local SQLite file otherwise. Credentials come from ``DATABASE_URL`` only.

Writes replace the whole table with the combined rows. Incremental counting
stays in the country snapshot tally; a second run must not add those rows on
top of the table again.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from ml.paths import use_postgres

COLUMNS = (
    "topic_id", "topic_name", "country_code", "year", "paper_count", "fractional_count",
)

_INSERT = (
    "INSERT INTO topic_country_year "
    "(topic_id, topic_name, country_code, year, paper_count, fractional_count) "
    "VALUES (%s, %s, %s, %s, %s, %s)"
)
_SELECT = (
    "SELECT topic_id, topic_name, country_code, year, paper_count, fractional_count "
    "FROM topic_country_year_v ORDER BY topic_id, country_code, year"
)


def _require_dsn() -> str:
    dsn = os.environ.get("DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError("DATABASE_URL is required")
    return dsn


def _connect(migrate: bool = False):
    """Open Postgres. ``migrate`` applies ``db/migrations`` once before a write."""
    dsn = _require_dsn()
    import psycopg

    conn = psycopg.connect(dsn)
    if not migrate:
        return conn
    try:
        from ml.store import migration_sql
        with conn.cursor() as cur:
            for stmt in migration_sql():
                cur.execute(stmt)
        conn.commit()
    except Exception:
        conn.close()
        raise
    return conn


def _tuples(rows: list[dict]) -> list[tuple]:
    return [tuple(row[col] for col in COLUMNS) for row in rows]


def _as_rows(fetched) -> list[dict]:
    rows = []
    for topic_id, name, code, year, papers, frac in fetched:
        rows.append({
            "topic_id": str(topic_id),
            "topic_name": str(name),
            "country_code": str(code),
            "year": int(year),
            "paper_count": int(papers),
            "fractional_count": float(frac),
        })
    return rows


def replace_topic_country_year(rows: list[dict], conn=None) -> None:
    """Replace every row. Does not DROP the table (the migration owns the DDL)."""
    own = conn is None
    if own:
        conn = _connect(migrate=True)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM topic_country_year")
            payload = _tuples(rows)
            if payload:
                cur.executemany(_INSERT, payload)
        if hasattr(conn, "commit"):
            conn.commit()
    except Exception:
        if hasattr(conn, "rollback"):
            conn.rollback()
        raise
    finally:
        if own:
            conn.close()


def read_topic_country_year(conn=None) -> list[dict]:
    """Rows from ``topic_country_year_v``, ordered like the SQLite writer."""
    own = conn is None
    if own:
        conn = _connect(migrate=False)
    try:
        with conn.cursor() as cur:
            cur.execute(_SELECT)
            fetched = cur.fetchall()
    finally:
        if own:
            conn.close()
    return _as_rows(fetched)


def read_sqlite(path: str | Path) -> list[dict] | None:
    """Rows from the SQLite file, or None when the file is missing or unreadable.

    An existing table with no rows returns ``[]`` so callers do not fall back
    to a stale snapshot.
    """
    path = Path(path)
    if not path.is_file():
        return None
    try:
        con = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            names = {row[0] for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')")}
            source = "topic_country_year_v" if "topic_country_year_v" in names else (
                "topic_country_year" if "topic_country_year" in names else None)
            if source is None:
                return None
            fetched = con.execute(
                "SELECT topic_id, topic_name, country_code, year, paper_count, fractional_count "
                f"FROM {source}"
            ).fetchall()
        finally:
            con.close()
    except sqlite3.Error:
        return None
    rows = _as_rows(fetched)
    rows.sort(key=lambda r: (r["topic_id"], r["country_code"], r["year"]))
    return rows


__all__ = [
    "COLUMNS",
    "read_sqlite",
    "read_topic_country_year",
    "replace_topic_country_year",
    "use_postgres",
]
