"""Upsert OpenAlex JSONL into Postgres (schema: db/migrations/0001_init.sql).

Idempotent: re-loading the same file changes nothing. Returns the set of
publication years touched, which drives dirty-window re-mining.
"""
from __future__ import annotations

import argparse
import json
import os
from collections.abc import Iterable, Iterator
from pathlib import Path

from .parse import ParsedWork, parse_work

UPSERT_WORK = """
INSERT INTO works (work_id, title, abstract, pub_year, pub_date, cited_by, n_authors,
                   doi, openalex_url, oa_url, updated_date)
VALUES (%(work_id)s, %(title)s, %(abstract)s, %(pub_year)s, %(pub_date)s, %(cited_by)s,
        %(n_authors)s, %(doi)s, %(openalex_url)s, %(oa_url)s, %(updated_date)s)
ON CONFLICT (work_id) DO UPDATE SET
  title = EXCLUDED.title, abstract = COALESCE(EXCLUDED.abstract, works.abstract),
  pub_year = EXCLUDED.pub_year, pub_date = EXCLUDED.pub_date, cited_by = EXCLUDED.cited_by,
  n_authors = EXCLUDED.n_authors, doi = EXCLUDED.doi, oa_url = EXCLUDED.oa_url,
  updated_date = EXCLUDED.updated_date, loaded_at = now()
"""
UPSERT_TOPIC = """
INSERT INTO topics (topic_id, display_name, subfield, field, domain)
VALUES (%(topic_id)s, %(display_name)s, %(subfield)s, %(field)s, %(domain)s)
ON CONFLICT (topic_id) DO UPDATE SET display_name = EXCLUDED.display_name,
  subfield = EXCLUDED.subfield, field = EXCLUDED.field, domain = EXCLUDED.domain
"""
UPSERT_AUTHOR = """
INSERT INTO authors (author_id, display_name, institution, country)
VALUES (%(author_id)s, %(display_name)s, %(institution)s, %(country)s)
ON CONFLICT (author_id) DO UPDATE SET display_name = EXCLUDED.display_name,
  institution = COALESCE(EXCLUDED.institution, authors.institution),
  country = COALESCE(EXCLUDED.country, authors.country)
"""


def iter_jsonl(path: Path) -> Iterator[ParsedWork]:
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                pw = parse_work(json.loads(line))
            except json.JSONDecodeError:
                continue
            if pw:
                yield pw


def load(conn, works: Iterable[ParsedWork], batch: int = 500) -> set[int]:
    """Upsert parsed works; child rows of each work are replaced wholesale."""
    years: set[int] = set()
    buf: list[ParsedWork] = []

    def flush() -> None:
        if not buf:
            return
        with conn.cursor() as cur:
            cur.executemany(UPSERT_WORK, [w.work for w in buf])
            topics = {t["topic_id"]: t for w in buf for t in w.topics}
            authors = {a["author_id"]: a for w in buf for a in w.authors}
            if topics:
                cur.executemany(UPSERT_TOPIC, list(topics.values()))
            if authors:
                cur.executemany(UPSERT_AUTHOR, list(authors.values()))
            ids = [w.work["work_id"] for w in buf]
            for t in ("work_topics", "work_authors", "work_countries"):
                cur.execute(f"DELETE FROM {t} WHERE work_id = ANY(%s)", (ids,))
            cur.executemany(
                "INSERT INTO work_topics VALUES (%(work_id)s, %(topic_id)s, %(score)s)",
                [r for w in buf for r in w.work_topics])
            cur.executemany(
                "INSERT INTO work_authors VALUES (%(work_id)s, %(author_id)s, %(author_pos)s)",
                [r for w in buf for r in w.work_authors])
            cur.executemany(
                "INSERT INTO work_countries VALUES (%s, %s)",
                [(w.work["work_id"], c) for w in buf for c in sorted(w.countries)])
        conn.commit()
        buf.clear()

    for pw in works:
        years.add(pw.work["pub_year"])
        buf.append(pw)
        if len(buf) >= batch:
            flush()
    flush()
    return years


def main() -> None:
    import psycopg

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", type=Path)
    ap.add_argument("--dsn", default=os.environ.get("DATABASE_URL"))
    a = ap.parse_args()
    with psycopg.connect(a.dsn) as conn:
        years = load(conn, iter_jsonl(a.input))
    print(f"loaded; years touched: {sorted(years)}")


if __name__ == "__main__":
    main()
