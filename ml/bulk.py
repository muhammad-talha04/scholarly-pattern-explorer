"""Stratified bulk fetch from OpenAlex, then the resumable batched indexer.

    python -m ml.cli bulk --target 70000 --start 2015-01 --out data/bulk_works.jsonl
    python -m ml.cli bulk --target 70000 --index          # fetch (resumes), then embed + upsert

Rules
- Even spread: new papers are assigned per calendar month in [start, end] so that
  stored + new is as even as possible (months already well covered get fewer). Each month is fetched with
  ``from/to_publication_date`` + ``has_abstract:true`` and a seeded random
  ``sample`` so the month is not dominated by the most-cited papers.
- Dedupe against ``exclude_ids`` (the work_ids already stored) and against
  everything already in the output file, so re-runs and resumes never double up.
- Polite: ``OPENALEX_API_KEY`` (or ``mailto`` via ``OPENALEX_EMAIL``), a minimum
  gap between requests, exponential backoff on 429 / 5xx / network errors.
- Only abstracts of at least ``min_abstract_chars`` (default 200) characters.
- Resumable: works are appended to ``out`` as JSONL (v2 rows, no ``raw``); per-month
  fetched/quota is kept in ``state``; a restart skips full months and tops up short ones.
- Sampling rate per month (OpenAlex total vs papers held) goes to ``sampling_rates``.
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


def quotas(month_list: list[str], target: int, existing: dict[str, int] | None = None) -> dict[str, int]:
    """New papers to fetch per month so the *total* per month ends up as even as possible.

    Water-filling: find the level L where sum(max(0, L - existing[m])) == target;
    months already above L get 0. Leftover units go to the emptiest months first.
    """
    ex = {m: int((existing or {}).get(m, 0)) for m in month_list}
    if target <= 0:
        return {m: 0 for m in month_list}
    lo, hi = 0, max(ex.values()) + target
    while lo < hi:   # largest L with fill(L) <= target
        mid = (lo + hi + 1) // 2
        if sum(max(0, mid - e) for e in ex.values()) <= target:
            lo = mid
        else:
            hi = mid - 1
    q = {m: max(0, lo - e) for m, e in ex.items()}
    left = target - sum(q.values())
    for m in sorted(month_list, key=lambda m: (ex[m] + q[m], m)):
        if left <= 0:
            break
        q[m] += 1
        left -= 1
    return q


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
    return json.loads(path.read_text()) if path.exists() else {}


def _read_ids(path: Path) -> set[str]:
    ids = set()
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    ids.add(json.loads(line)["id"])
    return ids


# Computer Science (OpenAlex field 17) articles only. Without the field filter the loader sampled all of science.
SCOPE = "primary_topic.field.id:fields/17,type:article"
FILTER = "from_publication_date:{lo},to_publication_date:{hi},has_abstract:true," + SCOPE


def fetch(target: int, out: str | Path, state: str | Path | None = None, start: str = "2015-01",
          end: str | None = None, exclude_ids: set[str] | None = None, client: OpenAlexClient | None = None,
          seed: int = 42, oversample: float = 1.3, existing_by_month: dict[str, int] | None = None,
          min_abstract_chars: int = 200, rates_sink=None) -> FetchResult:
    """Fetch about ``target`` new works with abstracts so each month's total is even. Resumable.

    State file: ``{"quota": {month: n}, "months": {month: {"fetched", "quota", "attempts",
    "openalex_total"}}}``. Quotas are fixed on the first run (so loading papers between
    runs does not shift them). A month is done only when fetched >= quota; a short
    month is topped up on the next run with a new sample seed. ``rates_sink(month,
    openalex_total, sampled, filter)`` records the per-month sampling rate.
    """
    from pipeline.ingest import SELECT, normalize

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    state_path = Path(state) if state else out.with_suffix(".state.json")
    st = _load_state(state_path)
    st.pop("done", None)   # pre-review state format
    client = client or OpenAlexClient()
    exclude = {i.rsplit("/", 1)[-1] for i in (exclude_ids or set())}
    have = _read_ids(out)
    existing_by_month = existing_by_month or {}
    if not st.get("quota"):
        st["quota"] = quotas(months(start, end), target, existing_by_month)
    st.setdefault("months", {})
    res = FetchResult()
    with open(out, "a", encoding="utf-8") as fh:
        for mo, want in st["quota"].items():
            ms = st["months"].setdefault(mo, {"fetched": 0, "quota": want, "attempts": 0})
            if ms["fetched"] >= want:
                res.months_done += 1
                continue
            lo, hi = month_bounds(mo)
            flt = FILTER.format(lo=lo, hi=hi)
            if ms.get("openalex_total") is None:
                meta = client.get({"filter": flt, "per-page": 1, "select": "id"}).get("meta") or {}
                ms["openalex_total"] = int(meta.get("count") or 0)
            need = want - ms["fetched"]
            got, page = 0, 1
            sample = min(MAX_SAMPLE, max(need, int(need * oversample) + len(exclude) // len(st["quota"]) + 1))
            while got < need:
                data = client.get({"filter": flt, "sample": sample, "seed": seed + ms["attempts"],
                                   "per-page": PER_PAGE, "page": page, "select": SELECT})
                results = data.get("results") or []
                for w in results:
                    row = normalize(w)
                    row.pop("raw", None)
                    ab = row.get("abstract") or ""
                    if len(ab.strip()) < min_abstract_chars or row["id"] in exclude or row["id"] in have:
                        continue
                    have.add(row["id"])
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                    got += 1
                    if got >= need:
                        break
                if len(results) < PER_PAGE or page * PER_PAGE >= sample:
                    break
                page += 1
            fh.flush()
            ms["fetched"] += got
            ms["attempts"] += 1
            if ms["fetched"] < want:
                res.short_months[mo] = want - ms["fetched"]
            else:
                res.months_done += 1
            res.fetched += got
            if rates_sink is not None:
                rates_sink(mo, ms["openalex_total"], existing_by_month.get(mo, 0) + ms["fetched"],
                           flt + f",min_abstract_chars:{min_abstract_chars}")
            state_path.write_text(json.dumps(st, indent=1))
            log.info("%s: %d/%d (OpenAlex total %d)", mo, ms["fetched"], want, ms["openalex_total"])
    res.requests = client.requests
    return res


@dataclass
class BackfillResult:
    missing: int = 0
    updated: int = 0
    not_found: int = 0
    requests: int = 0


def backfill_dates(store, client: OpenAlexClient | None = None, batch: int = 50,
                   dry_run: bool = False) -> BackfillResult:
    """Set meta.publication_date on stored papers that lack it. Metadata only.

    Looks ids up in OpenAlex ``batch`` at a time (``filter=openalex_id:a|b|...``,
    max 50 per OpenAlex OR-filter). Each batch is written as soon as it returns,
    so a rerun resumes where it stopped. Ids OpenAlex does not return are stored as
    ``publication_date: null`` so they are not asked for again (idempotent).
    """
    batch = max(1, min(int(batch), 50))
    todo = store.ids_missing_publication_date()
    res = BackfillResult(missing=len(todo))
    if dry_run or not todo:
        return res
    client = client or OpenAlexClient()
    for i in range(0, len(todo), batch):
        chunk = todo[i:i + batch]
        data = client.get({"filter": "openalex_id:" + "|".join(chunk), "per-page": batch,
                           "select": "id,publication_date"})
        found = {(w.get("id") or "").rsplit("/", 1)[-1]: w.get("publication_date")
                 for w in data.get("results") or []}
        dates = {wid: found.get(wid) for wid in chunk}
        res.not_found += sum(1 for wid in chunk if wid not in found)
        res.updated += store.set_publication_dates(dates)
        log.info("backfill-dates: %d/%d", min(i + batch, len(todo)), len(todo))
    res.requests = client.requests
    return res
