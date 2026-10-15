"""Emerging topics: year-over-year growth from the topic × country × year table.

The table has columns:

    topic_id, topic_name, country_code, year, paper_count, fractional_count

``load_topic_rows`` reads that table when it is present (Postgres when
``use_postgres()`` is true and no path was passed, otherwise the SQLite file,
then the ``topic_country_year`` list on the snapshot). Until then it builds
the same rows from ``data/works_v2.jsonl``. Counts are additive,
so a twice-monthly run can sum the new works onto the previous rows
(``combine_rows``) and match a full recompute. The scheduled pipeline already
does that inside ``country_stats`` once the table exists; this loader just
switches over.
"""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import mean, median

COLUMNS = ("topic_id", "topic_name", "country_code", "year", "paper_count", "fractional_count")


def _norm_row(row: dict) -> dict | None:
    if any(k not in row or row[k] is None for k in COLUMNS):
        return None
    try:
        year = int(row["year"])
        papers = int(row["paper_count"])
        frac = float(row["fractional_count"])
    except (TypeError, ValueError):
        return None
    topic_id = str(row["topic_id"]).strip()
    name = str(row["topic_name"]).strip()
    code = str(row["country_code"]).strip().upper()
    if not topic_id or not name or not code:
        return None
    return {"topic_id": topic_id, "topic_name": name, "country_code": code,
            "year": year, "paper_count": papers, "fractional_count": frac}


def _short_topic_id(value: str) -> str:
    text = str(value).strip()
    return text.rsplit("/", 1)[-1] if text else text


def topic_pairs(work: dict) -> list[tuple[str, str]]:
    """``(topic_id, topic_name)`` for one work. Names stand in for ids when that is all we have."""
    refs = work.get("topic_refs")
    raw_topics = None if refs else (work.get("raw") or {}).get("topics")
    out: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(tid, name):
        if tid is None:
            return
        tid_s = _short_topic_id(str(tid))
        name_s = str(name or tid_s).strip()
        if not tid_s or tid_s in seen:
            return
        seen.add(tid_s)
        out.append((tid_s, name_s or tid_s))

    if refs:
        for ref in refs:
            if isinstance(ref, dict):
                add(ref.get("id") or ref.get("name"), ref.get("name") or ref.get("id"))
        return out
    if raw_topics:
        for topic in raw_topics:
            if isinstance(topic, dict):
                add(topic.get("id") or topic.get("display_name"),
                    topic.get("display_name") or topic.get("name") or topic.get("id"))
            elif topic:
                add(topic, topic)
        if out:
            return out
    for name in work.get("topics") or []:
        if isinstance(name, dict):
            add(name.get("id") or name.get("display_name"),
                name.get("display_name") or name.get("name") or name.get("id"))
        elif name:
            add(name, name)
    return out


def _countries(work: dict) -> list[str]:
    if "countries" in work:
        raw = work.get("countries") or []
    else:
        raw = []
        for author in work.get("authorships") or []:
            raw.extend(author.get("countries") or [])
    out: list[str] = []
    for code in raw:
        if not code:
            continue
        text = str(code).strip().upper()
        if text and text not in out:
            out.append(text)
    return out


def _as_work(work) -> dict:
    if hasattr(work, "to_dict"):
        d = work.to_dict()
        d.setdefault("year", d.get("pub_year"))
        d.setdefault("id", d.get("work_id"))
        return d
    return work


def rows_from_works(works) -> list[dict]:
    """Same six columns as ``topic_country_year``. A paper with N countries adds 1 and 1/N."""
    acc: dict[tuple, dict] = {}
    for work in works:
        d = _as_work(work)
        year = d.get("year", d.get("pub_year"))
        try:
            year = int(year)
        except (TypeError, ValueError):
            continue
        countries = _countries(d)
        topics = topic_pairs(d)
        if not countries or not topics:
            continue
        share = 1.0 / len(countries)
        for tid, name in topics:
            for code in countries:
                key = (tid, code, year)
                cell = acc.get(key)
                if cell is None:
                    cell = {"topic_id": tid, "topic_name": name, "country_code": code,
                            "year": year, "paper_count": 0, "fractional_count": 0.0}
                    acc[key] = cell
                cell["paper_count"] += 1
                cell["fractional_count"] += share
                cell["topic_name"] = name or cell["topic_name"]
    return [acc[k] for k in sorted(acc)]


def combine_rows(previous: list[dict], new: list[dict]) -> list[dict]:
    """Add a monthly batch onto the previous aggregate. Same result as counting the union once."""
    acc: dict[tuple, dict] = {}
    for row in list(previous) + list(new):
        norm = _norm_row(row)
        if norm is None:
            continue
        key = (norm["topic_id"], norm["country_code"], norm["year"])
        cell = acc.get(key)
        if cell is None:
            acc[key] = dict(norm)
            continue
        cell["paper_count"] += norm["paper_count"]
        cell["fractional_count"] += norm["fractional_count"]
        if norm["topic_name"]:
            cell["topic_name"] = norm["topic_name"]
    return [acc[k] for k in sorted(acc)]


def _read_db(path: Path) -> list[dict] | None:
    if not path.is_file():
        return None
    try:
        con = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            names = {r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')")}
            source = "topic_country_year_v" if "topic_country_year_v" in names else (
                "topic_country_year" if "topic_country_year" in names else None)
            if source is None:
                return None
            fetched = con.execute(
                f"SELECT topic_id, topic_name, country_code, year, paper_count, fractional_count "
                f"FROM {source}").fetchall()
        finally:
            con.close()
    except sqlite3.Error:
        return None
    rows = []
    for topic_id, name, code, year, papers, frac in fetched:
        norm = _norm_row({"topic_id": topic_id, "topic_name": name, "country_code": code,
                          "year": year, "paper_count": papers, "fractional_count": frac})
        if norm is not None:
            rows.append(norm)
    return rows or None


def _read_snapshot(path: Path) -> list[dict] | None:
    if not path.is_file():
        return None
    try:
        snap = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    raw = snap.get("topic_country_year") if isinstance(snap, dict) else None
    if not raw:
        return None
    rows = [n for n in (_norm_row(r) for r in raw if isinstance(r, dict)) if n is not None]
    return rows or None


def load_topic_rows(snapshot_path: str | Path | None = None,
                    db_path: str | Path | None = None,
                    works_path: str | Path | None = None) -> tuple[list[dict], str]:
    """Prefer the typed table, then the snapshot list, then works JSONL.

    Pass a path to force the SQLite / snapshot / works chain. With every path
    left as ``None``, Postgres is consulted first when ``use_postgres()`` is
    true; otherwise the repo-root SQLite default from ``ml.paths`` is used.
    """
    from .paths import country_snapshot, topic_country_year_db, use_postgres

    if db_path is None and snapshot_path is None and works_path is None and use_postgres():
        try:
            from pipeline.aggregate_store import read_topic_country_year
            fetched = read_topic_country_year()
        except Exception:
            fetched = None
        if fetched:
            rows = [n for n in (_norm_row(r) for r in fetched) if n is not None]
            if rows:
                return rows, "table"

    db = Path(db_path) if db_path is not None else topic_country_year_db()
    table = _read_db(db)
    if table:
        return table, "table"
    snap = Path(snapshot_path) if snapshot_path is not None else country_snapshot()
    listed = _read_snapshot(snap)
    if listed:
        return listed, "snapshot"
    from .papers import default_works_path
    path = Path(works_path) if works_path is not None else default_works_path()
    if path is None or not Path(path).exists():
        return [], "none"
    # Read the JSONL dicts directly so topic ids on ``raw.topics`` / ``topic_refs`` survive.
    # ``Paper.from_record`` keeps display names only.
    works = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                works.append(json.loads(line))
    return rows_from_works(works), "works"


def robust_growth(series: list[float], smoothing: float = 5.0, cap: float = 2.0) -> float:
    """Smoothed year-over-year growth. ``min(mean, median)`` damps a one-off spike."""
    if len(series) < 2:
        return 0.0
    steps = [min(cap, max(-1.0, (b + smoothing) / (a + smoothing) - 1.0))
             for a, b in zip(series, series[1:])]
    return float(min(mean(steps), median(steps)))


def rank_emerging(rows: list[dict], *, country: str | None = None, last_year: int | None = None,
                  years: int = 3, smoothing: float = 5.0, cap: float = 2.0,
                  min_total: float = 20, min_last: float = 5, limit: int = 20) -> list[dict]:
    """Rank topics by robust growth over the last complete years.

    With no country, the series is the sum of ``fractional_count`` (a paper counts once).
    With a country, the series is ``paper_count`` for that country (whole papers).
    """
    code = country.strip().upper() if country and country.strip() else None
    last = last_year if last_year is not None else date.today().year - 1
    span = list(range(last - years, last + 1))
    names: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    cells: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
    for row in rows:
        norm = _norm_row(row)
        if norm is None:
            continue
        if code and norm["country_code"] != code:
            continue
        tid = norm["topic_id"]
        names[tid][norm["topic_name"]] += norm["paper_count"] or 1
        bucket = cells[tid][norm["year"]]
        bucket[0] += norm["fractional_count"]
        bucket[1] += norm["paper_count"]

    ranked = []
    for tid, by_year in cells.items():
        use_papers = code is not None
        series = [(by_year.get(y) or [0.0, 0.0])[1 if use_papers else 0] for y in span]
        volume = float(sum(series))
        if volume < min_total or series[-1] < min_last:
            continue
        growth = robust_growth(series, smoothing=smoothing, cap=cap)
        if growth <= 0:
            continue
        name_counts = names[tid]
        topic_name = max(name_counts, key=lambda n: (name_counts[n], n))
        frac_total = float(sum((by_year.get(y) or [0.0, 0.0])[0] for y in span))
        paper_total = int(round(volume))
        where = f" in {code}" if code else ""
        explanation = (
            f"{topic_name}{where} grew about {growth:.0%} a year from {span[0]} to {span[-1]}, "
            f"across {paper_total} papers."
        )
        ranked.append({
            "topic_id": tid,
            "topic_name": topic_name,
            "topic": topic_name,
            "country": code,
            "growth_rate": round(growth, 4),
            "growth_score": round(growth, 4),
            "paper_count": paper_total,
            "fractional_count": round(frac_total, 4),
            "window_start": span[0],
            "window_end": span[-1],
            "explanation": explanation,
        })
    ranked.sort(key=lambda r: (-r["growth_score"], -r["paper_count"], r["topic_name"]))
    return ranked[:limit]
