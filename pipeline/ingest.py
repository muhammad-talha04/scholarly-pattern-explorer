"""Incremental OpenAlex ingestion for v2.

Pulls only works published since the last successful run, adds the fields v2
needs (abstract, DOI, open-access link, countries), and merges them into the
existing JSONL without duplicates. Free: uses the public OpenAlex API.

    python -m pipeline.ingest --out data/works_v2.jsonl --state data/ingest_state.json

Sample mode (even coverage): one seeded OpenAlex `sample` per month, sized by a
quota CSV (month,from,to,openalex_count,quota) so every month is drawn at the
same rate. Reruns with the same seed and CSV give the same corpus.

    python -m pipeline.ingest --quota-csv deploy/sampling/monthly_quota.csv \
        --out data/works_sample.jsonl --manifest data/sample_manifest.json
"""
from __future__ import annotations
import argparse, csv, json, os, re, time
from datetime import date, timedelta
from pathlib import Path
import requests

API = "https://api.openalex.org/works"
_PLACEHOLDER_DOI = re.compile(r"10\.1234(?:/|$)", re.IGNORECASE)


def _public_url(url: str | None) -> str | None:
    if not isinstance(url, str) or not url.strip() or _PLACEHOLDER_DOI.search(url):
        return None
    return url
SELECT = ("id,doi,display_name,publication_year,publication_date,cited_by_count,"
          "topics,authorships,abstract_inverted_index,open_access,primary_location")


def abstract_from_index(inv: dict | None) -> str | None:
    """OpenAlex stores abstracts as {word: [positions]}; rebuild the text."""
    if not inv:
        return None
    pos = {p: w for w, ps in inv.items() for p in ps}
    return " ".join(pos[i] for i in sorted(pos)) or None


def topic_refs(w: dict) -> list[dict]:
    """One {id, name} per OpenAlex topic. Id is the short OpenAlex id when present."""
    refs, seen = [], set()
    for t in w.get("topics") or []:
        if not isinstance(t, dict):
            continue
        name = t.get("display_name")
        raw_id = t.get("id")
        tid = raw_id.rsplit("/", 1)[-1] if isinstance(raw_id, str) and raw_id else None
        if not tid and not name:
            continue
        key = tid or name
        if key in seen:
            continue
        seen.add(key)
        refs.append({"id": key, "name": name or key})
    return refs


def normalize(w: dict) -> dict:
    countries = sorted({c for a in w.get("authorships") or []
                        for c in (a.get("countries") or [])
                        + [i.get("country_code") for i in a.get("institutions") or []] if c})
    loc = w.get("primary_location") or {}
    oa = w.get("open_access") or {}
    return {
        "id": w["id"].rsplit("/", 1)[-1],
        "title": w.get("display_name"),
        "year": w.get("publication_year"),
        "date": w.get("publication_date"),
        "cited_by": w.get("cited_by_count") or 0,
        "doi": _public_url(w.get("doi")),
        "abstract": abstract_from_index(w.get("abstract_inverted_index")),
        "original_url": _public_url(oa.get("oa_url")) or _public_url(loc.get("landing_page_url")) or _public_url(w.get("doi")),
        "openalex_url": w["id"],
        "authors": [n for a in w.get("authorships") or [] if (n := (a.get("author") or {}).get("display_name"))],
        "countries": countries,
        "topics": [t["display_name"] for t in w.get("topics") or [] if t.get("display_name")],
        "topic_refs": topic_refs(w),
        "raw": w,  # kept so build_db.py / Tom's ml/ can read the original shape
    }


def merge(out: Path, new: list[dict]) -> int:
    """Append only works not already on disk. Returns how many were added."""
    seen = set()
    if out.exists():
        with out.open(encoding="utf-8") as fh:
            seen = {json.loads(l)["id"] for l in fh if l.strip()}
    added = 0
    with out.open("a", encoding="utf-8") as fh:
        for r in new:
            if r["id"] not in seen:
                seen.add(r["id"]); added += 1
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return added


def fetch(since: str, filters: list[str], max_records: int, session=requests):
    cursor, got = "*", 0
    params = _auth({"filter": ",".join([f"from_publication_date:{since}", "type:article", *filters]),
                    "per-page": "200", "select": SELECT})
    while cursor and got < max_records:
        data = _get(session, {**params, "cursor": cursor})
        for w in data.get("results", []):
            got += 1
            yield normalize(w)
        cursor = (data.get("meta") or {}).get("next_cursor")
        time.sleep(0.15)


SAMPLE_SEED = 20261016  # fixed: changing it changes the whole corpus
SAMPLE_MAX = 10000      # OpenAlex caps one sample at 10k; page paging tops out there too


def _auth(params: dict) -> dict:
    if os.environ.get("OPENALEX_MAILTO"):
        params["mailto"] = os.environ["OPENALEX_MAILTO"]
    if os.environ.get("OPENALEX_API_KEY"):
        params["api_key"] = os.environ["OPENALEX_API_KEY"]
    return params


def _get(session, params: dict) -> dict:
    for attempt in range(6):
        r = session.get(API, params=params, timeout=60)
        if r.status_code == 200:
            return r.json()
        if r.status_code in (401, 403):
            raise SystemExit(f"OpenAlex HTTP {r.status_code}: set OPENALEX_API_KEY")
        time.sleep(2 ** attempt)
    raise SystemExit(f"OpenAlex kept failing: HTTP {r.status_code}")


def read_quotas(path: Path) -> list[dict]:
    rows = []
    with path.open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            q = int(r["quota"])
            if q > SAMPLE_MAX:
                raise SystemExit(f"{r['month']}: quota {q} exceeds the OpenAlex sample cap {SAMPLE_MAX}")
            rows.append({"month": r["month"], "from": r["from"], "to": r["to"],
                         "openalex_count": int(r["openalex_count"]), "quota": q})
    return rows


def fetch_sample(frm: str, to: str, n: int, seed: int, filters: list[str], session=requests):
    """Seeded random sample of n works published in [frm, to]. Sample results
    can't be cursor-paged, so this pages by number (200 per page)."""
    params = _auth({"filter": ",".join([f"from_publication_date:{frm}", f"to_publication_date:{to}",
                                         "type:article", *filters]),
                    "sample": str(n), "seed": str(seed), "per-page": "200", "select": SELECT})
    seen, page = set(), 1
    while len(seen) < n and (page - 1) * 200 < n:
        data = _get(session, {**params, "page": str(page)})
        results = data.get("results", [])
        if not results:
            break
        for w in results:
            r = normalize(w)
            if r["id"] not in seen:  # pages of one seeded sample shouldn't overlap; guard anyway
                seen.add(r["id"])
                yield r
        page += 1
        time.sleep(0.15)


def run_sample(a) -> int:
    out, manifest = Path(a.out), Path(a.manifest)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = json.loads(manifest.read_text()) if manifest.exists() else {}
    if done and (done.get("seed") != a.seed or done.get("filters") != a.filter):
        raise SystemExit("manifest was built with a different seed or filter; use a fresh --out/--manifest")
    done.update({"seed": a.seed, "filters": a.filter, "quota_csv": str(a.quota_csv)})
    months = done.setdefault("months", {})
    status = 0
    for q in read_quotas(Path(a.quota_csv)):
        if months.get(q["month"], {}).get("complete"):
            continue  # resumable: finished months are skipped
        batch, got = [], 0
        try:
            for r in fetch_sample(q["from"], q["to"], q["quota"], a.seed, a.filter):
                batch.append(r); got += 1
        except SystemExit as e:
            print(f"{q['month']}: stopped ({e}); will retry on next run")
            status = 1
            break
        added = merge(out, batch)
        months[q["month"]] = {**q, "fetched": got, "added": added, "complete": got >= q["quota"]}
        manifest.write_text(json.dumps(done, indent=1))
        print(f"{q['month']}: {got}/{q['quota']} fetched, {added} new")
        if got < q["quota"]:
            status = 1
    manifest.write_text(json.dumps(done, indent=1))
    return status


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/works_v2.jsonl")
    ap.add_argument("--state", default="data/ingest_state.json")
    ap.add_argument("--filter", action="append", default=["primary_topic.subfield.id:subfields/1702"])
    ap.add_argument("--first-lookback-days", type=int, default=365)
    ap.add_argument("--overlap-days", type=int, default=7, help="re-check recent days; duplicates are skipped")
    ap.add_argument("--max-records", type=int, default=50000)
    ap.add_argument("--quota-csv", help="sample mode: per-month quotas (see module docstring)")
    ap.add_argument("--seed", type=int, default=SAMPLE_SEED)
    ap.add_argument("--manifest", default="data/sample_manifest.json")
    a = ap.parse_args(argv)
    if a.quota_csv:
        return run_sample(a)
    out, state = Path(a.out), Path(a.state)
    out.parent.mkdir(parents=True, exist_ok=True)
    last = json.loads(state.read_text())["last_run"] if state.exists() else None
    since = (date.fromisoformat(last) - timedelta(days=a.overlap_days)) if last \
        else date.today() - timedelta(days=a.first_lookback_days)
    added, batch, failed = 0, [], None
    try:
        for r in fetch(since.isoformat(), a.filter, a.max_records):
            batch.append(r)
            if len(batch) >= 200:  # save each page as it arrives
                added += merge(out, batch); batch = []
    except SystemExit as e:
        failed = e
    added += merge(out, batch)
    if failed:  # keep what we got, but don't advance last_run so the gap is retried
        print(f"stopped early ({failed}); saved {added} works")
        return 1
    state.write_text(json.dumps({"last_run": date.today().isoformat(), "last_added": added}))
    print(f"since {since}: {added} new works")
    return 0 if added else 2


if __name__ == "__main__":
    raise SystemExit(main())
