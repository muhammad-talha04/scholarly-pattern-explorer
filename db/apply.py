"""Apply db/migrations/*.sql in filename order.

    DATABASE_URL=postgresql://... python -m db.apply

The API role in DATABASE_URL bypasses row level security. The migrations enable
RLS and add no policies, so the Supabase anon and authenticated roles cannot
read or write these tables.
"""
from __future__ import annotations

import os

from ml.store import migration_files, split_sql


def apply(dsn: str | None = None) -> list[str]:
    """Run every migration. Returns the filenames that were applied."""
    dsn = dsn or os.environ.get("DATABASE_URL")
    if not dsn:
        raise SystemExit("DATABASE_URL is required")
    import psycopg

    files = migration_files()
    if not files:
        raise SystemExit("no migrations found under db/migrations")
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            for path in files:
                for stmt in split_sql(path.read_text(encoding="utf-8")):
                    cur.execute(stmt)
    return [path.name for path in files]


def main() -> None:
    names = apply()
    for name in names:
        print(f"applied {name}")


if __name__ == "__main__":
    main()
