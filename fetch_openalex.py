"""
STEP 1-REAL: download real papers from OpenAlex into the same JSONL format.

Do this AFTER the fake-data pipeline already works end to end.

Get your free API key first (2 minutes):
  1. go to  https://openalex.org
  2. create an account, open your account settings, copy the API key
  3. put it in your terminal so you never paste it into code:
        Windows PowerShell :  $env:OPENALEX_API_KEY = "your-key-here"
        macOS / Linux      :  export OPENALEX_API_KEY="your-key-here"

Examples
--------
  python fetch_openalex.py --dry-run                       # show the URL, download nothing
  python fetch_openalex.py --count-only                    # how many papers match?
  python fetch_openalex.py --subfield-id 1702 --min-cited 5 --count-only
  python fetch_openalex.py --max-records 5000              # a small first pull
  python fetch_openalex.py --from-year 2000 --to-year 2026 --max-records 200000

Narrowing the slice (do this until --count-only prints a number you can
actually download; a broad filter gives generic, boring patterns):
  --subfield-id 1702                      Artificial Intelligence, not all of CS
  --topic-id T11512                       one single topic
  --min-cited 5                           drop papers nobody cited
  --extra-filter "authorships.institutions.country_code:ca"
  --extra-filter "language:en"            repeatable; each one ANDs with the rest

It saves progress to data/fetch_state.json, so if your internet drops you can
re-run the same command and it continues from the last cursor instead of
starting over.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

import requests

API = "https://api.openalex.org/works"

# Only ask for the fields we actually store. Smaller responses = faster and
# cheaper against your daily credit budget.
SELECT = "id,display_name,publication_year,cited_by_count,topics,authorships"


def build_params(args, cursor):
    filters = [f"publication_year:{args.from_year}-{args.to_year}", "type:article"]

    # Narrowest wins. topic < subfield < field, in size order.
    if args.topic_id:
        filters.append(f"primary_topic.id:topics/{args.topic_id}")
    elif args.subfield_id:
        filters.append(f"primary_topic.subfield.id:subfields/{args.subfield_id}")
    elif args.field_id:
        filters.append(f"primary_topic.field.id:fields/{args.field_id}")

    if args.min_cited:
        # OpenAlex only has a strict >, so subtract one to make it inclusive.
        filters.append(f"cited_by_count:>{args.min_cited - 1}")

    filters.extend(args.extra_filter or [])

    params = {
        "filter": ",".join(filters),
        "per-page": str(args.per_page),
        "select": SELECT,
        "cursor": cursor,
    }
    if args.mailto:
        params["mailto"] = args.mailto
    key = args.api_key or os.environ.get("OPENALEX_API_KEY")
    if key:
        params["api_key"] = key
    return params


def get_with_retry(params, tries=8):
    """
    Handle rate limits AND dropped connections politely instead of crashing.

    Two different things can go wrong on a long download:
      1. the server answers with an error code   (429 rate limit, 5xx outage)
      2. the connection dies mid-response        (ChunkedEncodingError,
         ConnectionError, ReadTimeout - very common on home internet)
    Both are temporary, so both get the same exponential backoff.
    """
    for attempt in range(1, tries + 1):
        wait = min(60, 2 ** attempt)
        try:
            r = requests.get(API, params=params, timeout=(15, 90))
        except requests.exceptions.RequestException as exc:
            print(f"  network hiccup ({type(exc).__name__}); "
                  f"waiting {wait}s (attempt {attempt}/{tries})")
            time.sleep(wait)
            continue

        if r.status_code == 200:
            try:
                return r.json()
            except ValueError:
                print(f"  truncated JSON; waiting {wait}s (attempt {attempt}/{tries})")
                time.sleep(wait)
                continue

        if r.status_code in (429, 500, 502, 503, 504):
            print(f"  HTTP {r.status_code}; waiting {wait}s (attempt {attempt}/{tries})")
            time.sleep(wait)
            continue

        print(f"HTTP {r.status_code}: {r.text[:300]}", file=sys.stderr)
        if r.status_code in (401, 403):
            print("Auth problem. Check OPENALEX_API_KEY, and see "
                  "https://help.openalex.org/api/authentication/", file=sys.stderr)
        raise SystemExit(1)

    print("\nGave up after repeated errors. Your progress is saved - run the same\n"
          "command WITHOUT --restart to carry on from where it stopped.",
          file=sys.stderr)
    raise SystemExit(1)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/works_real.jsonl")
    ap.add_argument("--state", default="data/fetch_state.json")
    ap.add_argument("--from-year", type=int, default=2000)
    ap.add_argument("--to-year", type=int, default=2026)
    ap.add_argument("--field-id", default="17",
                    help="OpenAlex field id; 17 is Computer Science. "
                         "Check yours at https://api.openalex.org/fields?search=computer")
    ap.add_argument("--subfield-id", default=None,
                    help="narrower than a field, e.g. 1702 = Artificial Intelligence. "
                         "List them: https://api.openalex.org/subfields?search=artificial")
    ap.add_argument("--topic-id", default=None,
                    help="narrowest of all, e.g. T11512. "
                         "List them: https://api.openalex.org/topics?search=data+mining")
    ap.add_argument("--min-cited", type=int, default=0,
                    help="keep only works cited at least this many times")
    ap.add_argument("--extra-filter", action="append", default=[],
                    help='raw OpenAlex filter; repeatable. '
                         'e.g. --extra-filter "authorships.institutions.country_code:ca"')
    ap.add_argument("--per-page", type=int, default=200, help="200 is the maximum")
    ap.add_argument("--max-records", type=int, default=50000)
    ap.add_argument("--mailto", default=None, help="your email = politer, higher limits")
    ap.add_argument("--api-key", default=None)
    ap.add_argument("--sleep", type=float, default=0.15, help="pause between pages")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--count-only", action="store_true",
                    help="ask the API how many works match, download nothing")
    ap.add_argument("--restart", action="store_true", help="ignore saved cursor")
    args = ap.parse_args()

    Path("data").mkdir(exist_ok=True)
    state_path = Path(args.state)
    cursor, written = "*", 0
    if state_path.exists() and not args.restart:
        saved = json.loads(state_path.read_text())
        cursor, written = saved.get("cursor", "*"), saved.get("written", 0)
        print(f"resuming from saved cursor, {written:,} records already on disk")

    if args.dry_run:
        p = build_params(args, cursor)
        p.pop("api_key", None)                      # never print your key
        print("filter:", p["filter"], "\n")
        print("URL that would be called:\n")
        print(f"{API}?{urlencode(p)}\n")
        print("Paste that into a browser to see the raw JSON. "
              "Look at meta.count to see how many papers match.")
        print("Or skip the browser:  python fetch_openalex.py --count-only")
        return

    if args.count_only:
        p = build_params(args, "*")
        p["per-page"] = "1"
        n = (get_with_retry(p).get("meta") or {}).get("count", 0)
        print(f"filter: {build_params(args, '*')['filter']}")
        print(f"\n{n:,} works match.")
        if n > 500_000:
            print("That is a very broad slice. Your download would be a biased first\n"
                  "slice of it, and the mined patterns will be generic. Narrow it with\n"
                  "--subfield-id, --min-cited, or a country/institution --extra-filter.")
        elif n < 5_000:
            print("That is quite narrow - you may not have enough papers per window.\n"
                  "Widen it, or plan to mine with --min-support 0.01 or lower.")
        else:
            print("Good size: you can download most or all of it.")
        return

    if not (args.api_key or os.environ.get("OPENALEX_API_KEY")):
        print("WARNING: no API key found. Without a key the daily allowance is tiny.\n"
              "         Set OPENALEX_API_KEY first - see the notes at the top of this file.\n")

    mode = "w" if (args.restart or not Path(args.out).exists()) else "a"
    with open(args.out, mode, encoding="utf-8") as fh:
        while cursor and written < args.max_records:
            data = get_with_retry(build_params(args, cursor))
            results = data.get("results", [])
            if not results:
                break
            for rec in results:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            written += len(results)
            fh.flush()

            cursor = (data.get("meta") or {}).get("next_cursor")
            state_path.write_text(json.dumps({"cursor": cursor, "written": written}))
            total = (data.get("meta") or {}).get("count", 0)
            print(f"  {written:>8,} / {min(total, args.max_records):,} records")
            time.sleep(args.sleep)

    print(f"\nsaved {written:,} records -> {args.out}")
    print(f"next:  python build_db.py --input {args.out}")


if __name__ == "__main__":
    main()

