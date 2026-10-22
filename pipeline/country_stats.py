"""Per-country and per-topic analytics, shaped like schemas.CountryStats.

Incremental: the previous snapshot's counters are combined with the new works
only, so a steady-state run never re-reads the whole corpus. The first run
after this aggregate existed seeds it once from `--corpus` when that snapshot
has no topic-country-year counters. Counting is fractional by default (a paper
with N distinct countries gives each 1/N); full counting is also kept.

Each run also refreshes the topic × country × year aggregate
(`topic_country_year`: topic_id, topic_name, country_code, year, paper_count,
fractional_count) inside the snapshot and rewrites the SQLite table next to it.
"""
from __future__ import annotations
import argparse, json, os, sqlite3, sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from countries import COUNTRIES  # noqa: E402  (existing ISO table in repo root)
from ml.paths import resolve, topic_country_year_db  # noqa: E402

KEYS = ("by_year", "frac", "topics", "topic_years", "topic_countries",
        "pairs_frac", "pairs_1n", "topic_names", "tcy_papers", "tcy_frac",
        "by_date", "frac_date", "papers_date")
# papers_date: {"all": {"YYYY-MM-DD": n}} papers with at least one country, the
# denominator for share of corpus.
# by_date / frac_date: {country: {"YYYY-MM-DD": count}} (whole / fractional), used for
# the equal-period growth metric. Papers without a publication date are skipped there.

MIN_PAPERS = 30            # both periods need at least this many (active counting mode)
PARTIAL_YEARS = {2024}     # corpus starts mid-Oct 2024: any window touching it is hidden
SHARE_FIELDS = ("share_pct", "share_prev_pct", "share_change_pp", "share_reason")
GROWTH_FIELDS = ("growth_pct", "growth_reason", "growth_cur_count", "growth_prev_count",
                 "growth_window_start", "growth_window_end")

TOPIC_COUNTRY_YEAR_COLUMNS = (
    "topic_id", "topic_name", "country_code", "year", "paper_count", "fractional_count",
)


def distinct_countries(codes) -> list[str]:
    """ISO codes in first-seen order, blanks dropped, duplicates collapsed."""
    out: list[str] = []
    for c in codes or []:
        if not c:
            continue
        code = str(c).strip().upper()
        if code and code not in out:
            out.append(code)
    return out


def fractional_weights(codes) -> dict[str, float]:
    """1/N for each of N distinct countries. No country → empty (sums to 0)."""
    cs = distinct_countries(codes)
    if not cs:
        return {}
    share = 1.0 / len(cs)
    return {c: share for c in cs}


def countries_of(work: dict) -> list[str]:
    """Distinct countries on one work.

    Normalized works already carry `countries`. A raw OpenAlex work (no such
    key) is read from authorships so duplicate countries across authors still
    count once.
    """
    if "countries" in work:
        return distinct_countries(work.get("countries"))
    raw = []
    for author in work.get("authorships") or []:
        raw.extend(author.get("countries") or [])
        raw.extend(inst.get("country_code") for inst in (author.get("institutions") or []))
    return distinct_countries(raw)


def work_topic_refs(work: dict) -> list[tuple[str, str]]:
    """(topic_id, topic_name) pairs, one per topic. Names stand in for ids on legacy rows."""
    refs = work.get("topic_refs")
    if not refs:
        raw_topics = (work.get("raw") or {}).get("topics")
        if raw_topics:
            from pipeline.ingest import topic_refs
            refs = topic_refs({"topics": raw_topics})
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    if refs:
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            tid = ref.get("id") or ref.get("name")
            name = ref.get("name") or tid
            if not tid or str(tid) in seen:
                continue
            seen.add(str(tid))
            out.append((str(tid), str(name)))
        return out
    for name in work.get("topics") or []:
        if name and str(name) not in seen:
            seen.add(str(name))
            out.append((str(name), str(name)))
    return out


def tally(works) -> dict:
    t = {k: defaultdict(Counter) for k in KEYS}
    pairs = Counter()
    for w in works:
        cs = countries_of(w)
        weights = fractional_weights(cs)
        yr = str(w.get("year"))
        tops = [x for x in (w.get("topics") or []) if x]  # all topics, same as the gap finder fallback
        for c in cs:
            t["by_year"][c][yr] += 1
            t["frac"][c][yr] += weights[c]
            t["topics"][c].update(tops)
        for tp in tops:
            t["topic_years"][tp][yr] += 1
            for c in cs:
                t["topic_countries"][tp][c] += weights[c]
        n = len(cs)
        for i, a in enumerate(cs):
            for b in cs[i + 1:]:
                pairs[f"{a}-{b}"] += 1
                # default: every paper adds exactly 1 across its pairs
                t["pairs_frac"]["all"][f"{a}-{b}"] += 2 / (n * (n - 1))
                t["pairs_1n"]["all"][f"{a}-{b}"] += 1 / n
        date = _iso_date(w.get("date") or w.get("publication_date"))
        if date and cs:
            t["papers_date"]["all"][date] += 1
        if date:
            for c in cs:
                t["by_date"][c][date] += 1
                t["frac_date"][c][date] += weights[c]
        if cs:
            for tid, name in work_topic_refs(w):
                t["topic_names"][tid][name] += 1
                for c in cs:
                    key = f"{c}|{yr}"
                    t["tcy_papers"][tid][key] += 1
                    t["tcy_frac"][tid][key] += weights[c]
    t["pairs"] = pairs
    return t


def combine(prev: dict | None, new: dict) -> dict:
    if not prev:
        return new
    out = {}
    for k in KEYS:
        m = defaultdict(Counter, {c: Counter(v) for c, v in (prev.get(k) or {}).items()})
        for c, cnt in new[k].items():
            m[c].update(cnt)
        out[k] = m
    out["pairs"] = Counter(prev.get("pairs") or {}) + new["pairs"]
    return out


def _iso_date(v) -> str | None:
    s = str(v or "")[:10]
    if len(s) == 10 and s[4] == "-" and s[7] == "-" and s[:4].isdigit():
        return s
    return None


def growth_window(t: dict) -> dict | None:
    """Year-to-date window ending at the newest publication date in the data (not today).

    current = Jan 1 .. cutoff of the cutoff's year; previous = the same dates a year earlier.
    """
    dates = [d for k in ("by_date",) for cs in (t.get(k) or {}).values() for d in cs]
    if not dates:
        return None
    end = max(dates)
    y = int(end[:4])
    md = end[5:]
    if md == "02-29":  # previous year may not have it
        md = "02-28"
    return {"cur_start": f"{y}-01-01", "cur_end": end,
            "prev_start": f"{y - 1}-01-01", "prev_end": f"{y - 1}-{md}",
            "years": (y - 1, y)}


def growth_for(dates: dict | None, win: dict | None) -> dict:
    """Equal-period growth for one series of {date: count}. Spec: docs/growth_spec.md."""
    empty = dict.fromkeys(GROWTH_FIELDS)
    if not win:
        empty["growth_reason"] = "too_few_papers"
        return empty
    dates = dates or {}
    cur = sum(v for d, v in dates.items() if win["cur_start"] <= d <= win["cur_end"])
    prev = sum(v for d, v in dates.items() if win["prev_start"] <= d <= win["prev_end"])
    out = {"growth_pct": None, "growth_reason": None,
           "growth_cur_count": round(cur, 2), "growth_prev_count": round(prev, 2),
           "growth_window_start": win["cur_start"], "growth_window_end": win["cur_end"]}
    if PARTIAL_YEARS & set(win["years"]):
        out["growth_reason"] = "partial_year"
    elif cur < MIN_PAPERS or prev < MIN_PAPERS:
        out["growth_reason"] = "too_few_papers"
    else:
        out["growth_pct"] = round(100 * (cur - prev) / prev, 1)
    return out


def _window_sum(dates: dict | None, start: str, end: str) -> float:
    return sum(v for d, v in (dates or {}).items() if start <= d <= end)


def share_for(dates: dict | None, totals: dict | None, win: dict | None) -> dict:
    """Share of corpus: this country's papers / all papers in the same window.

    Same window and rules as growth_for. The country count (active counting mode)
    must be >= 30 in both periods, and windows touching 2024 are hidden.
    Denominator: papers with at least one country. In fractional mode the shares
    of all countries add up to 100%; in full mode they can add up to more.
    """
    out = dict.fromkeys(SHARE_FIELDS)
    if not win:
        out["share_reason"] = "too_few_papers"
        return out
    cur = _window_sum(dates, win["cur_start"], win["cur_end"])
    prev = _window_sum(dates, win["prev_start"], win["prev_end"])
    tot_cur = _window_sum(totals, win["cur_start"], win["cur_end"])
    tot_prev = _window_sum(totals, win["prev_start"], win["prev_end"])
    if PARTIAL_YEARS & set(win["years"]):
        out["share_reason"] = "partial_year"
    elif cur < MIN_PAPERS or prev < MIN_PAPERS or not tot_cur or not tot_prev:
        out["share_reason"] = "too_few_papers"
    else:
        sc, sp = cur / tot_cur, prev / tot_prev
        share_pct = round(sc * 100, 2)
        share_prev_pct = round(sp * 100, 2)
        # Difference of the displayed percents, so 4.77 - 4.03 is 0.74.
        out.update(share_pct=share_pct, share_prev_pct=share_prev_pct,
                   share_change_pp=round(share_pct - share_prev_pct, 2))
    return out


def to_stats(t: dict, top_n: int = 5, counting: str = "fractional") -> list[dict]:
    src = t["frac"] if counting == "fractional" else t["by_year"]
    dsrc = (t.get("frac_date") if counting == "fractional" else t.get("by_date")) or {}
    win = growth_window(t)
    totals = (t.get("papers_date") or {}).get("all") or {}
    rows = []
    for code, years in src.items():
        rows.append({"code": code, "name": COUNTRIES.get(code, (code,))[0],
                     "papers": round(sum(years.values()), 2),
                     **growth_for(dsrc.get(code), win),
                     **share_for(dsrc.get(code), totals, win),
                     "top_topics": [n for n, _ in t["topics"][code].most_common(top_n)],
                     "counting": counting})
    return sorted(rows, key=lambda r: -r["papers"])


def _collab(pairs) -> list[dict]:
    return [{"source": p.split("-")[0], "target": p.split("-")[1], "papers": round(n, 2)}
            for p, n in Counter(pairs).most_common(200)]  # weights rounded for display only


def _topic_name(t: dict, topic_id: str) -> str:
    counts = (t.get("topic_names") or {}).get(topic_id) or {}
    if not counts:
        return topic_id
    return max(counts.items(), key=lambda item: item[1])[0]


def topic_country_year_rows(t: dict) -> list[dict]:
    """Rows for the topic × country × year aggregate. One paper adds 1 and 1/N."""
    papers = t.get("tcy_papers") or {}
    fracs = t.get("tcy_frac") or {}
    rows = []
    for topic_id in set(papers) | set(fracs):
        whole = papers.get(topic_id) or {}
        frac = fracs.get(topic_id) or {}
        name = _topic_name(t, topic_id)
        for key in set(whole) | set(frac):
            country, _, year_s = key.partition("|")
            if not year_s.isdigit():
                continue
            rows.append({
                "topic_id": topic_id,
                "topic_name": name,
                "country_code": country,
                "year": int(year_s),
                "paper_count": int(whole.get(key) or 0),
                "fractional_count": float(frac.get(key) or 0),
            })
    rows.sort(key=lambda r: (r["topic_id"], r["country_code"], r["year"]))
    return rows


def write_topic_country_year(rows: list[dict], db_path: Path) -> None:
    """Rewrite the aggregate table from the combined snapshot (not from the corpus)."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = db_path.with_suffix(db_path.suffix + ".tmp")
    con = sqlite3.connect(tmp)
    try:
        con.execute("DROP VIEW IF EXISTS topic_country_year_v")
        con.execute("DROP TABLE IF EXISTS topic_country_year")
        con.execute(
            """
            CREATE TABLE topic_country_year (
                topic_id TEXT NOT NULL,
                topic_name TEXT NOT NULL,
                country_code TEXT NOT NULL,
                year INTEGER NOT NULL,
                paper_count INTEGER NOT NULL,
                fractional_count REAL NOT NULL,
                PRIMARY KEY (topic_id, country_code, year)
            )
            """
        )
        con.execute(
            """
            CREATE VIEW topic_country_year_v AS
            SELECT topic_id, topic_name, country_code, year, paper_count, fractional_count
            FROM topic_country_year
            """
        )
        con.executemany(
            """
            INSERT INTO topic_country_year
                (topic_id, topic_name, country_code, year, paper_count, fractional_count)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [tuple(r[col] for col in TOPIC_COUNTRY_YEAR_COLUMNS) for r in rows],
        )
        con.commit()
    finally:
        con.close()
    tmp.replace(db_path)


def snapshot(t: dict) -> dict:
    return {
        "tally": t,
        "countries": to_stats(t),
        "countries_full": to_stats(t, counting="full"),
        "collaborations": _collab(t["pairs_frac"]["all"]),
        "collaborations_full": _collab(t["pairs"]),
        "collaborations_1n": _collab(t["pairs_1n"]["all"]),
        # Michal's gap finder: {topic: {year: count}} and top countries per topic
        "topic_year_counts": {tp: dict(ys) for tp, ys in t["topic_years"].items()},
        "topic_top_countries": {tp: [[c, round(n, 2)] for c, n in cs.most_common(5)]
                                for tp, cs in t["topic_countries"].items()},
        "topic_country_year": topic_country_year_rows(t),
    }


def output_paths(out: str, table: str | None) -> tuple[Path, Path]:
    """Snapshot JSON and the topic-country-year SQLite file.

    Relative paths are anchored to the repo root (ml/paths.resolve), same as
    COUNTRY_SNAPSHOT. An explicit absolute --out keeps the sqlite beside it
    unless TOPIC_COUNTRY_YEAR_DB or --table says otherwise.
    """
    out_p = resolve(out)
    if table:
        table_p = resolve(table)
    elif os.getenv("TOPIC_COUNTRY_YEAR_DB"):
        table_p = topic_country_year_db()
    else:
        table_p = out_p.with_name("topic_country_year.sqlite")
    return out_p, table_p


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--new", required=True, help="JSONL of works added this run")
    ap.add_argument("--prev", help="previous snapshot JSON")
    ap.add_argument("--out", default="data/country_snapshot.json")
    ap.add_argument("--table", help="SQLite file for topic_country_year (default: beside --out)")
    ap.add_argument("--dates", help="JSONL of {date, countries} for every work; rebuilds the "
                    "date counters (by_date/frac_date) when --prev predates them")
    ap.add_argument("--corpus", help="full works JSONL; read once if --prev has no topic-country-year counters")
    a = ap.parse_args(argv)
    new_path = resolve(a.new)
    prev_path = resolve(a.prev) if a.prev else None
    corpus_path = resolve(a.corpus) if a.corpus else None
    dates_path = resolve(a.dates) if a.dates else None
    with open(new_path, encoding="utf-8") as fh:
        new = tally(json.loads(l) for l in fh if l.strip())
    prev = json.loads(prev_path.read_text())["tally"] if prev_path and prev_path.exists() else None
    combined = combine(prev, new)
    # Snapshots written before this aggregate existed have country counters but no
    # topic × country × year cells. Seed those cells from the corpus once; later
    # runs only add --new on top of the stored counters.
    if prev is not None and "tcy_papers" not in prev and corpus_path and corpus_path.is_file():
        with open(corpus_path, encoding="utf-8") as fh:
            seeded = tally(json.loads(l) for l in fh if l.strip())
        for key in ("topic_names", "tcy_papers", "tcy_frac"):
            combined[key] = seeded[key]
    if dates_path and dates_path.is_file():
        with open(dates_path, encoding="utf-8") as fh:
            seeded = tally(json.loads(l) for l in fh if l.strip())
        for key in ("by_date", "frac_date", "papers_date"):
            combined[key] = seeded[key]
    elif prev is not None and "papers_date" not in prev and corpus_path and corpus_path.is_file():
        with open(corpus_path, encoding="utf-8") as fh:
            seeded = tally(json.loads(l) for l in fh if l.strip())
        for key in ("by_date", "frac_date", "papers_date"):
            combined[key] = seeded[key]
    snap = snapshot(combined)
    out, table = output_paths(a.out, a.table)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snap))
    write_topic_country_year(snap["topic_country_year"], table)
    print(f"{len(snap['countries'])} countries, {len(snap['topic_year_counts'])} topics, "
          f"{len(snap['topic_country_year'])} topic-country-year rows")


if __name__ == "__main__":
    main()
