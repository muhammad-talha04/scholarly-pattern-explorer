"""Incremental OpenAlex data refresher (v4 - no premium filters required).

v4 changes (Sept 2026)
----------------------
  * "Plan upgrade required" answers are detected on the FIRST attempt and the
    script stops immediately instead of waiting through the whole backoff.
  * --subfield-id lets the refresh use the SAME slice as the original download
    (fetch_openalex.py --subfield-id 1702 --min-cited 20). Mixing slices in one
    JSONL silently changes what your patterns mean.
  * --lookback-days N re-scans the last N days every run. OpenAlex often adds a
    paper days or weeks AFTER its publication date, so a 1-day window misses
    papers. Duplicates are skipped, so re-scanning is safe.
  * --overlap-days now defaults to 30 for the same reason.

Why this version exists
-----------------------
The old version synced with `from_updated_date`, which OpenAlex only allows for
premium keys. A free key gets rejected with HTTP 429 / 403 on EVERY attempt, so
no amount of waiting or backoff ever helped. This version:

  * syncs by `from_publication_date` (free for everyone) by default,
  * can still TRY the premium `from_updated_date` filter once and fall back
    automatically (--sync-mode auto),
  * never retries an error that retrying cannot fix,
  * tells you plainly which mode it used.

Run:
  python refresh.py                      # normal daily run
  python refresh.py --count-only         # how many works would be pulled?
  python refresh.py --dry-run            # print the URL, download nothing
  python refresh.py --sync-mode auto     # try premium filter first, then fall back

Exit codes (refresh_daily.ps1 relies on these):
  0 = new data was appended
  2 = ran fine, nothing new
  1 = real failure
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

import requests

API = "https://api.openalex.org/works"

# Same fields as fetch_openalex.py so the JSONL stays uniform and build_db.py
# keeps finding the keys it expects.
SELECT = "id,display_name,publication_year,cited_by_count,topics,authorships"
DEFAULT_FILTERS = ["type:article"]
FIELD_FILTER = "primary_topic.field.id:fields/17"   # Computer Science


class ApiError(RuntimeError):
    """An HTTP error from OpenAlex that carries its status code."""

    def __init__(self, status: int, body: str = "") -> None:
        super().__init__(f"OpenAlex returned HTTP {status}: {body[:200]}")
        self.status = status


def load_env() -> None:
    env_path = Path(__file__).parent.absolute() / ".env"
    if not env_path.exists():
        print(f"note: no .env file at {env_path}")
        return
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        print(f"loaded environment from {env_path}")
    except OSError as exc:
        print(f"warning: could not read .env ({exc})")


def load_state(path: Path, fallback_days: int) -> str:
    if path.exists():
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            state = {}
        saved = state.get("last_sync_date") or state.get("last_updated_date")
        if saved:
            return saved
    return (date.today() - timedelta(days=fallback_days)).isoformat()


def save_state(path: Path, last_date: str, cursor: str | None, appended: int,
               mode: str) -> None:
    existing: dict = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            existing = {}
    existing.update({
        "last_sync_date": last_date,
        "last_updated_date": last_date,      # kept for backwards compatibility
        "refresh_cursor": cursor,
        "refresh_appended": appended,
        "refresh_mode": mode,
        "refresh_ran_at": datetime.now().isoformat(timespec="seconds"),
    })
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    tmp.replace(path)


def build_params(args, from_date: str, cursor: str, mode: str) -> dict:
    filters = list(DEFAULT_FILTERS)
    if args.subfield_id:
        # Narrower than the field filter, so it replaces it.
        filters.append(f"primary_topic.subfield.id:subfields/{args.subfield_id}")
    elif not args.no_field_filter:
        filters.append(FIELD_FILTER)
    if mode == "updated":
        filters.append(f"from_updated_date:{from_date}")
    else:
        filters.append(f"from_publication_date:{from_date}")
    if args.min_cited:
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


def session_for(args) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": f"openalex-pattern-miner/1.0 "
                      f"(mailto:{args.mailto or 'anonymous'})",
        "Accept": "application/json",
    })
    return s


def get_with_retry(session: requests.Session, params: dict, tries: int = 4) -> dict:
    """Retry transient problems only. Raises ApiError with the status code."""
    last_status = 0
    last_body = ""
    for attempt in range(1, tries + 1):
        wait = min(30, 2 ** attempt)
        try:
            r = session.get(API, params=params, timeout=(15, 90))
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

        last_status, last_body = r.status_code, r.text

        if r.status_code in (400, 401, 403):
            # Bad filter or auth. Retrying can never fix these.
            raise ApiError(r.status_code, r.text)

        # OpenAlex uses HTTP 429 for TWO different problems:
        #   (a) "slow down"             -> waiting helps
        #   (b) "Plan upgrade required" -> waiting NEVER helps
        # Always read the body before deciding to wait.
        body_lower = r.text[:500].lower()
        if r.status_code == 429 and ("upgrade" in body_lower
                                     or "premium" in body_lower):
            raise ApiError(r.status_code, r.text)

        if r.status_code == 429 or 500 <= r.status_code < 600:
            if attempt == tries:
                break
            retry_after = r.headers.get("Retry-After", "")
            pause = int(retry_after) if retry_after.isdigit() else wait
            print(f"  HTTP {r.status_code}; waiting {pause}s "
                  f"(attempt {attempt}/{tries})")
            time.sleep(pause)
            continue

        raise ApiError(r.status_code, r.text)

    raise ApiError(last_status or 599, last_body)


def seen_ids(path: Path) -> set[str]:
    ids: set[str] = set()
    if not path.exists():
        return ids
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                wid = json.loads(line).get("id")
            except ValueError:
                continue
            if wid:
                ids.add(wid)
    return ids


def refresh(args) -> int:
    state_path = Path(args.state)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.parent.mkdir(parents=True, exist_ok=True)

    from_date = load_state(state_path, args.fallback_days)
    if args.since:
        from_date = args.since
    if args.lookback_days:
        from_date = (date.today() - timedelta(days=args.lookback_days)).isoformat()
    elif args.overlap_days:
        from_date = (date.fromisoformat(from_date)
                     - timedelta(days=args.overlap_days)).isoformat()

    mode = "updated" if args.sync_mode in ("auto", "updated") else "published"
    print(f"fetching works with {mode}_date >= {from_date} "
          f"(sync-mode: {args.sync_mode})")

    session = session_for(args)

    if args.dry_run or args.count_only:
        p = build_params(args, from_date, "*", mode)
        p.pop("api_key", None)
        print("filter:", p["filter"])
        if args.dry_run:
            print(f"\n{API}?{urlencode(p)}")
            return 2
        p = build_params(args, from_date, "*", mode)
        p["per-page"] = "1"
        n = (get_with_retry(session, p).get("meta") or {}).get("count", 0)
        print(f"\n{n:,} works match.")
        return 2

    if not (args.api_key or os.environ.get("OPENALEX_API_KEY")):
        print("note: no OPENALEX_API_KEY set; the daily allowance will be small.")

    known = seen_ids(out_path) if args.dedupe else set()
    if known:
        print(f"{len(known):,} works already on disk; duplicates will be skipped")

    cursor = "*"
    appended = 0
    pages = 0
    run_started = date.today().isoformat()

    with out_path.open("a", encoding="utf-8") as fh:
        while cursor and appended < args.max_records:
            try:
                data = get_with_retry(session, build_params(args, from_date,
                                                            cursor, mode))
            except ApiError as exc:
                # The premium filter is rejected with 429/403/400 no matter how
                # long we wait, so switch to the free filter and start over.
                if (args.sync_mode == "auto" and mode == "updated"
                        and exc.status in (400, 403, 429)):
                    print(f"  premium filter from_updated_date rejected "
                          f"(HTTP {exc.status}); "
                          f"falling back to from_publication_date")
                    mode = "published"
                    cursor = "*"
                    pages = 0
                    time.sleep(2)
                    continue
                raise

            results = data.get("results") or []
            if not results:
                break

            for work in results:
                wid = work.get("id")
                if args.dedupe and wid in known:
                    continue
                fh.write(json.dumps(work, ensure_ascii=False) + "\n")
                if wid:
                    known.add(wid)
                appended += 1
            fh.flush()

            pages += 1
            meta = data.get("meta") or {}
            cursor = meta.get("next_cursor")
            print(f"  page {pages:>4}   appended {appended:>7,}   "
                  f"matching {meta.get('count', 0):,}   (mode: {mode})")

            save_state(state_path, from_date, cursor, appended, mode)
            if cursor and appended < args.max_records:
                time.sleep(args.sleep)

    if appended >= args.max_records:
        print(f"hit --max-records ({args.max_records:,}); stopping for today.")

    # Only move the watermark forward once the run actually finished.
    save_state(state_path, run_started, None, appended, mode)
    print(f"\nappended {appended:,} new works -> {out_path}")
    return 0 if appended else 2


def main() -> int:
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="data/fetch_state.json")
    ap.add_argument("--output", default="data/works_real.jsonl")
    ap.add_argument("--sync-mode", choices=("published", "updated", "auto"),
                    default="published",
                    help="published = free filter (default); "
                         "updated = premium only; auto = try premium, fall back")
    ap.add_argument("--since", default=None,
                    help="override the saved watermark, e.g. 2026-08-01")
    ap.add_argument("--min-cited", type=int, default=0,
                    help="0 is sensible for fresh papers: they have no citations yet")
    ap.add_argument("--no-field-filter", action="store_true",
                    help="do not restrict to Computer Science (fields/17)")
    ap.add_argument("--extra-filter", action="append", default=[])
    ap.add_argument("--per-page", type=int, default=200, help="200 is the maximum")
    ap.add_argument("--max-records", type=int, default=50_000)
    ap.add_argument("--sleep", type=float, default=0.25)
    ap.add_argument("--subfield-id", default=None,
                    help="e.g. 1702 = Artificial Intelligence. Use the same "
                         "value your original download used.")
    ap.add_argument("--lookback-days", type=int, default=0,
                    help="ignore the watermark and scan the last N days")
    ap.add_argument("--fallback-days", type=int, default=7)
    ap.add_argument("--overlap-days", type=int, default=30)
    ap.add_argument("--mailto", default=os.environ.get("OPENALEX_MAILTO"))
    ap.add_argument("--api-key", default=None)
    ap.add_argument("--no-dedupe", dest="dedupe", action="store_false")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--count-only", action="store_true")
    args = ap.parse_args()

    if not args.mailto:
        print("warning: no OPENALEX_MAILTO set. Add it to .env; anonymous "
              "requests are throttled hard.")

    try:
        return refresh(args)
    except KeyboardInterrupt:
        print("\ninterrupted; progress was saved.", file=sys.stderr)
        return 1
    except ApiError as exc:
        print(f"refresh failed: {exc}", file=sys.stderr)
        if exc.status == 429:
            print("HTTP 429 on every attempt usually means the filter is not "
                  "allowed for your key, not that you are going too fast. "
                  "Run: python diagnose_429.py", file=sys.stderr)
        if exc.status in (401, 403):
            print("Auth problem: check OPENALEX_API_KEY in .env.", file=sys.stderr)
        return 1
    except Exception as exc:                                   # noqa: BLE001
        print(f"refresh failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
