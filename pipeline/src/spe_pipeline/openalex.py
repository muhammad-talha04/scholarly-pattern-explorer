"""Resumable OpenAlex /works downloader (ported from legacy/fetch_openalex.py).

Writes raw JSONL and saves the cursor after every page, so an interrupted run
continues where it stopped. ``--from-updated`` enables incremental pulls
(OpenAlex ``from_updated_date`` filter) for the scheduled job.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests

API = "https://api.openalex.org/works"
SELECT = (
    "id,doi,display_name,publication_year,publication_date,updated_date,cited_by_count,"
    "topics,authorships,abstract_inverted_index,open_access,best_oa_location"
)
RETRY_STATUS = {429, 500, 502, 503, 504}


def build_filters(args: argparse.Namespace) -> list[str]:
    f = [f"publication_year:{args.from_year}-{args.to_year}", "type:article"]
    if args.topic_id:
        f.append(f"primary_topic.id:topics/{args.topic_id}")
    elif args.subfield_id:
        f.append(f"primary_topic.subfield.id:subfields/{args.subfield_id}")
    elif args.field_id:
        f.append(f"primary_topic.field.id:fields/{args.field_id}")
    if args.min_cited:
        f.append(f"cited_by_count:>{args.min_cited - 1}")  # API only has strict >
    if args.from_updated:
        f.append(f"from_updated_date:{args.from_updated}")
    f.extend(args.extra_filter or [])
    return f


def build_params(args: argparse.Namespace, cursor: str) -> dict[str, str]:
    p = {
        "filter": ",".join(build_filters(args)),
        "per-page": str(args.per_page),
        "select": SELECT,
        "cursor": cursor,
    }
    if args.mailto or os.environ.get("OPENALEX_MAILTO"):
        p["mailto"] = args.mailto or os.environ["OPENALEX_MAILTO"]
    key = os.environ.get("OPENALEX_API_KEY")
    if key:
        p["api_key"] = key
    return p


def get_with_retry(session: requests.Session, params: dict[str, str], tries: int = 8,
                   sleep=time.sleep) -> dict[str, Any]:
    """Exponential backoff on rate limits, 5xx and dropped connections."""
    for attempt in range(1, tries + 1):
        wait = min(60, 2 ** attempt)
        try:
            r = session.get(API, params=params, timeout=(15, 90))
        except requests.exceptions.RequestException as exc:
            print(f"  network error {type(exc).__name__}; retry in {wait}s", file=sys.stderr)
            sleep(wait)
            continue
        if r.status_code == 200:
            try:
                return r.json()
            except ValueError:
                sleep(wait)
                continue
        if r.status_code in RETRY_STATUS:
            print(f"  HTTP {r.status_code}; retry in {wait}s", file=sys.stderr)
            sleep(wait)
            continue
        raise RuntimeError(f"OpenAlex HTTP {r.status_code}: {r.text[:300]}")
    raise RuntimeError("OpenAlex: gave up after repeated errors (progress saved)")


def fetch(args: argparse.Namespace, session: requests.Session | None = None) -> int:
    session = session or requests.Session()
    out, state_path = Path(args.out), Path(args.state)
    out.parent.mkdir(parents=True, exist_ok=True)
    cursor, written = "*", 0
    if state_path.exists() and not args.restart:
        s = json.loads(state_path.read_text())
        cursor, written = s.get("cursor") or "*", s.get("written", 0)
        if s.get("done"):
            print("previous run completed; use --restart for a fresh pull")
            return 0
    mode = "a" if (written and not args.restart) else "w"
    with out.open(mode, encoding="utf-8") as fh:
        while cursor and written < args.max_records:
            data = get_with_retry(session, build_params(args, cursor))
            results = data.get("results") or []
            if not results:
                cursor = None
                break
            for rec in results:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            written += len(results)
            fh.flush()
            cursor = (data.get("meta") or {}).get("next_cursor")
            state_path.write_text(json.dumps({"cursor": cursor, "written": written}))
            print(f"  {written:,} records")
            time.sleep(args.sleep)
    state_path.write_text(json.dumps({"cursor": cursor, "written": written,
                                      "done": cursor is None}))
    return written


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="data/works.jsonl")
    ap.add_argument("--state", default="data/fetch_state.json")
    ap.add_argument("--from-year", type=int, default=2000)
    ap.add_argument("--to-year", type=int, default=2026)
    ap.add_argument("--field-id", default="17")
    ap.add_argument("--subfield-id")
    ap.add_argument("--topic-id")
    ap.add_argument("--min-cited", type=int, default=0)
    ap.add_argument("--from-updated", help="YYYY-MM-DD, incremental pulls")
    ap.add_argument("--extra-filter", action="append", default=[])
    ap.add_argument("--per-page", type=int, default=200)
    ap.add_argument("--max-records", type=int, default=50_000)
    ap.add_argument("--mailto")
    ap.add_argument("--sleep", type=float, default=0.15)
    ap.add_argument("--restart", action="store_true")
    return ap


def main() -> None:
    n = fetch(parser().parse_args())
    print(f"saved {n:,} records")


if __name__ == "__main__":
    main()
