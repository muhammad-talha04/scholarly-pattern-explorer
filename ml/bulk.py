"""Stratified bulk fetch from OpenAlex, then the resumable batched indexer.

    python -m ml.cli bulk --target 70000 --start 2015-01 --out data/bulk_works.jsonl
    python -m ml.cli bulk --target 70000 --index          # fetch (resumes), then embed + upsert

Rules
- Even spread: the target is split evenly over every calendar month in
  [start, end]; leftovers go to the earliest months. Each month is fetched with
  ``from/to_publication_date`` + ``has_abstract:true`` and a seeded random
  ``sample`` so the month is not dominated by the most-cited papers.
- Dedupe against ``exclude_ids`` (the work_ids already stored) and against
  everything already in the output file, so re-runs and resumes never double up.
- Polite: ``OPENALEX_API_KEY`` (or ``mailto`` via ``OPENALEX_EMAIL``), a minimum
  gap between requests, exponential backoff on 429 / 5xx / network errors.
- Resumable: works are appended to ``out`` as JSONL (v2 rows, no ``raw``) and the
  finished months are recorded in ``state``; a restart skips finished months.
- Embedding is not done here; ``ml.indexer.index`` does it with the ML_EMBEDDER
  model and its ModelMismatch guard.
"""
from __future__ import annotations

import json
import logging
import os
import time
from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

log = logging.getLogger("spe.bulk")
API = "https://api.openalex.org/works"
PER_PAGE = 200
MAX_SAMPLE = 10_000   # OpenAlex caps sample size


def months(start: str, end: str | None = None) -> list[str]:
    """Inclusive list of 'YYYY-MM' from start to end (default: current month)."""
    y, m = map(int, start.split("-")[:2])
    ey, em = map(int, (end or date.today().strftime("%Y-%m")).split("-")[:2])
    out = []
    while (y, m) <= (ey, em):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    if not out:
        raise ValueError(f"empty range {start}..{end}")
    return out


def quotas(month_list: list[str], target: int) -> dict[str, int]:
    base, extra = divmod(target, len(month_list))
    return {mo: base + (1 if i < extra else 0) for i, mo in enumerate(month_list)}


def month_bounds(mo: str) -> tuple[str, str]:
    y, m = map(int, mo.split("-"))
    return f"{mo}-01", f"{mo}-{monthrange(y, m)[1]:02d}"


@dataclass
class FetchResult:
    fetched: int = 0
    requests: int = 0
    months_done: int = 0
    short_months: dict[str, int] = field(default_factory=dict)


class OpenAlexClient:
    def __init__(self, session=None, api_key: str | None = None, email: str | None = None,
                 min_interval: float = 0.12, max_retries: int = 6, sleep=time.sleep):
        if session is None:
            import requests
            session = requests.Session()
        self.s = session
        self.api_key = api_key if api_key is not None else os.getenv("OPENALEX_API_KEY")
        self.email = email if email is not None else os.getenv("OPENALEX_EMAIL")
        self.min_interval, self.max_retries, self.sleep = min_interval, max_retries, sleep
        self._last = 0.0
        self.requests = 0

    def get(self, params: dict) -> dict:
        params = dict(params)
        if self.api_key:
            params["api_key"] = self.api_key
        if self.email:
            params["mailto"] = self.email
        delay = 1.0
        for attempt in range(self.max_retries + 1):
            wait = self.min_interval - (time.monotonic() - self._last)
            if wait > 0:
                self.sleep(wait)
            self._last = time.monotonic()
            self.requests += 1
            try:
                r = self.s.get(API, params=params, timeout=60)
                status = r.status_code
            except Exception as exc:   # network error: back off and retry
                status, r = None, exc
            if status == 200:
                return r.json()
            if status is not None and status not in (429,) and status < 500:
                raise RuntimeError(f"OpenAlex {status}: {getattr(r, 'text', '')[:200]}")
            if attempt == self.max_retries:
                raise RuntimeError(f"OpenAlex failed after {attempt + 1} tries: {status or r}")
            retry_after = None
            try:
                retry_after = float(r.headers.get("Retry-After"))  # type: ignore[union-attr]
            except Exception:
                pass
            log.warning("OpenAlex %s, retrying in %.0fs", status or r, retry_after or delay)
            self.sleep(retry_after or delay)
            delay = min(delay * 2, 60)
        raise AssertionError("unreachable")


def _load_state(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {"done": {}}


def _read_ids(path: Path) -> set[str]:
    ids = set()
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    ids.add(json.loads(line)["id"])
    return ids


def fetch(target: int, out: str | Path, state: str | Path | None = None, start: str = "2015-01",
          end: str | None = None, exclude_ids: set[str] | None = None, client: OpenAlexClient | None = None,
          seed: int = 42, oversample: float = 1.3) -> FetchResult:
    """Fetch about ``target`` new works with abstracts, evenly per month. Resumable."""
    from pipeline.ingest import SELECT, normalize

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    state_path = Path(state) if state else out.with_suffix(".state.json")
    st = _load_state(state_path)
    client = client or OpenAlexClient()
    exclude = {i.rsplit("/", 1)[-1] for i in (exclude_ids or set())}
    have = _read_ids(out)
    res = FetchResult()
    q = quotas(months(start, end), target)
    with open(out, "a", encoding="utf-8") as fh:
        for mo, want in q.items():
            if mo in st["done"]:
                res.months_done += 1
                continue
            lo, hi = month_bounds(mo)
            got, page = 0, 1
            sample = min(MAX_SAMPLE, max(want, int(want * oversample) + len(exclude) // len(q)))
            while got < want:
                data = client.get({
                    "filter": f"from_publication_date:{lo},to_publication_date:{hi},has_abstract:true",
                    "sample": sample, "seed": seed, "per-page": PER_PAGE, "page": page,
                    "select": SELECT})
                results = data.get("results") or []
                for w in results:
                    row = normalize(w)
                    row.pop("raw", None)
                    if not row.get("abstract") or row["id"] in exclude or row["id"] in have:
                        continue
                    have.add(row["id"])
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                    got += 1
                    if got >= want:
                        break
                if len(results) < PER_PAGE or page * PER_PAGE >= sample:
                    break
                page += 1
            fh.flush()
            if got < want:
                res.short_months[mo] = want - got
            res.fetched += got
            res.months_done += 1
            st["done"][mo] = got
            state_path.write_text(json.dumps(st, indent=1))
            log.info("%s: %d/%d", mo, got, want)
    res.requests = client.requests
    return res
