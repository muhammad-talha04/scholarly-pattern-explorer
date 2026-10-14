"""
Tiny database adapter.

WHY THIS FILE EXISTS
--------------------
This project uses a real relational database. DuckDB is the recommended one
(fast, analytics-friendly, installs with one pip command). But if DuckDB is not
installed, everything still works on sqlite3, which ships inside Python itself.

You do not need to understand this file to use the project. It just gives the
rest of the code four simple methods: exec, many, df, script.
"""
from __future__ import annotations

import re
import sqlite3
import pandas as pd

try:
    import duckdb
    HAVE_DUCKDB = True
except ModuleNotFoundError:
    HAVE_DUCKDB = False

# Matches a plain "INSERT INTO some_table VALUES (?,?,?)" so that many() can
# swap in the fast bulk path. Anything more complicated falls back to the
# slow-but-always-correct row-by-row path.
_SIMPLE_INSERT = re.compile(
    r"^\s*INSERT\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)\s*"
    r"VALUES\s*\(\s*\?(?:\s*,\s*\?)*\s*\)\s*;?\s*$",
    re.IGNORECASE,
)


class DB:
    """One object that talks to either DuckDB or SQLite with the same methods."""

    def __init__(self, path: str, prefer: str = "duckdb", read_only: bool = False):
        self.kind = "duckdb" if (HAVE_DUCKDB and prefer == "duckdb") else "sqlite"
        path = str(path)
        if self.kind == "duckdb":
            self.path = path
            # read_only=True is what the web app uses: it can never damage the
            # database, and several read-only viewers can share one file.
            self.con = duckdb.connect(self.path, read_only=read_only)
        else:
            # keep a separate file name so the two engines never fight
            self.path = path[:-7] + ".sqlite" if path.endswith(".duckdb") else path
            self.con = sqlite3.connect(self.path)
            try:
                # faster writes; silently skipped on network drives that refuse it
                self.con.execute("PRAGMA journal_mode=WAL")
            except sqlite3.OperationalError:
                pass

    def exec(self, sql: str, params=None):
        """Run one statement. Use ? placeholders for values (both engines agree)."""
        return self.con.execute(sql, params) if params else self.con.execute(sql)

    def many(self, sql: str, rows, chunk: int = 100_000):
        """
        Insert many rows.

        WHY THIS IS NOT JUST executemany
        --------------------------------
        DuckDB is a column store. Handing it one row at a time through
        executemany() means one tiny transaction-ish operation per row, and on
        a few hundred thousand rows that takes tens of minutes. Handing it a
        whole pandas DataFrame at once takes seconds, because it copies whole
        columns straight into its own storage.

        So: if the SQL is a plain "INSERT INTO table VALUES (?,?,...)", we
        register the rows as a temporary DataFrame and let the database read
        them in bulk. If anything about that path fails (odd data type, older
        DuckDB), we print a note and finish the remaining rows the slow way -
        never re-inserting a row that already went in.
        """
        rows = list(rows)
        if not rows:
            return

        done = 0
        match = _SIMPLE_INSERT.match(sql)
        if self.kind == "duckdb" and match:
            table = match.group(1)
            try:
                cols = self._columns(table)
                for start in range(0, len(rows), chunk):
                    part = rows[start:start + chunk]
                    frame = pd.DataFrame(part, columns=cols)
                    self.con.register("_bulk_rows", frame)
                    self.con.execute(f"INSERT INTO {table} SELECT * FROM _bulk_rows")
                    self.con.unregister("_bulk_rows")
                    done = start + len(part)
                return
            except Exception as exc:                                  # noqa: BLE001
                print(f"  (bulk load unavailable: {type(exc).__name__}: {exc}\n"
                      f"   finishing the remaining rows the slow way)")

        for start in range(done, len(rows), chunk):
            self.con.executemany(sql, rows[start:start + chunk])

    def _columns(self, table: str) -> list[str]:
        """Column names of a table, in definition order."""
        got = self.con.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = ? ORDER BY ordinal_position", [table]
        ).fetchall()
        if not got:
            raise RuntimeError(f"table {table!r} not found")
        return [r[0] for r in got]

    def df(self, sql: str, params=None) -> pd.DataFrame:
        """Run a SELECT and get a pandas DataFrame back."""
        if self.kind == "duckdb":
            # A DuckDB connection must not be used by two threads at once, and
            # Streamlit serves every browser tab (and every rerun) on its own
            # thread. Sharing one connection is what made view switches hang.
            # A cursor is a cheap, independent handle on the same database.
            cur = self.con.cursor()
            try:
                if params:
                    cur.execute(sql, params)
                else:
                    cur.execute(sql)
                return cur.df()
            finally:
                cur.close()
        return pd.read_sql_query(sql, self.con, params=params or [])

    def script(self, sql_text: str):
        """Run a whole .sql file (statements separated by semicolons)."""
        for stmt in sql_text.split(";"):
            if stmt.strip():
                self.con.execute(stmt)

    def commit(self):
        if self.kind == "sqlite":
            self.con.commit()

    def close(self):
        self.commit()
        self.con.close()
