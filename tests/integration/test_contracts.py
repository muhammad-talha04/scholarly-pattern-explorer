"""Contracts between #3 (pipeline/), #2 (ml/) and #1 (apps/api schemas + routes)."""
import json

import pytest
from fastapi.testclient import TestClient

from app import ml_bridge
from app.main import app
from app.schemas import (AskResponse, Collaboration, CountryStats, PaperDetail, PaperSummary, Pattern, Run,
                         SearchResponse)
from ml.embeddings import HashEmbedder
from ml.gaps import counts_from_works, find_gaps, load_inputs
from ml.incremental import IncrementalMiner
from ml.papers import Paper, read_works
from ml.service import MLService, SummaryCache
from ml.store import LocalStore
from pipeline import country_stats as cs
from pipeline.ingest import merge, normalize

COUNTINGS = ["full", "fractional"]

V2_REQUIRED = {"id": str, "title": str, "year": int, "cited_by": int, "authors": list,
               "countries": list, "topics": list}


def ingest(path, raw):
    return merge(path, [normalize(w) for w in raw])


@pytest.fixture
def works_v2(tmp_path, raw_batches):
    p = tmp_path / "works_v2.jsonl"
    b1, b2 = raw_batches
    assert ingest(p, b1) == 5
    assert ingest(p, b2) == 3  # W5 duplicate skipped
    return p


def rows(path):
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


# ---------- pipeline ingest -> works_v2.jsonl -> ml/ ----------

def test_works_v2_rows_have_contract_fields(works_v2):
    rs = rows(works_v2)
    assert len(rs) == len({r["id"] for r in rs}) == 8
    for r in rs:
        for k, t in V2_REQUIRED.items():
            assert isinstance(r[k], t), (r["id"], k)
        assert r["id"].startswith("W") and "/" not in r["id"]
        assert r["countries"] == sorted(set(r["countries"]))


def test_ml_reads_works_v2_as_v2_rows(works_v2):
    papers = {p.work_id: p for p in read_works(works_v2)}
    assert set(papers) == {f"W{i}" for i in range(1, 9)}
    w1 = papers["W1"]
    assert w1.pub_year == 2021 and w1.title.startswith("Transformers")
    assert w1.abstract == "We apply transformer language models to protein folding."
    assert w1.countries == ["CA", "PK"] and w1.authors == ["Author 1.0", "Author 1.1"]
    assert w1.topics == ["Protein Folding", "Deep Learning"]
    assert w1.best_original_url == "https://example.org/w1.pdf"
    raw = next(r for r in rows(works_v2) if r["id"] == "W1")
    assert w1.openalex_url == raw["openalex_url"]  # same URL whichever side builds it


def test_ml_works_path_prefers_v2(tmp_path, monkeypatch, works_v2):
    from ml.papers import default_works_path
    monkeypatch.delenv("ML_WORKS_PATH", raising=False)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "works_v2.jsonl").write_text(works_v2.read_text())
    (tmp_path / "data" / "works.jsonl").write_text("")
    assert default_works_path(tmp_path).name == "works_v2.jsonl"


# ---------- country_stats -> schemas.CountryStats ----------

@pytest.mark.parametrize("counting", COUNTINGS)
def test_country_stats_validates_both_counting_modes(works_v2, counting):
    stats = cs.to_stats(cs.tally(rows(works_v2)), counting=counting)
    assert stats
    for s in stats:
        m = CountryStats.model_validate(s)
        assert m.counting == counting
    pk = next(s for s in stats if s["code"] == "PK")
    assert pk["name"] == "Pakistan"
    if counting == "full":
        assert pk["papers"] == 4  # W1, W4, W5, W7


@pytest.mark.parametrize("counting", COUNTINGS)
def test_country_stats_snapshot_file_validates(tmp_path, works_v2, counting):
    out = tmp_path / "snap.json"
    cs.main(["--new", str(works_v2), "--out", str(out)])
    snap = json.loads(out.read_text())
    key = "countries_full" if counting == "full" else "countries"
    if True:
        assert snap[key]
        for s in snap[key]:
            assert CountryStats.model_validate(s).counting == counting
    for c in snap["collaborations"]:
        Collaboration.model_validate(c)


def test_country_stats_fractional_shares_sum_to_one_per_paper(works_v2):
    """pipeline/country_stats.py: each paper with countries contributes exactly 1 in total."""
    for w in rows(works_v2):
        t = cs.tally([w])
        total = sum(sum(v.values()) for v in t["frac"].values())
        assert total == pytest.approx(1.0 if w["countries"] else 0.0)
    works = rows(works_v2)
    t = cs.tally(works)
    assert sum(sum(v.values()) for v in t["frac"].values()) == pytest.approx(
        sum(1 for w in works if w["countries"]))
    full = sum(sum(v.values()) for v in t["by_year"].values())
    assert full == sum(len(w["countries"]) for w in works)


def test_fractional_shares_sum_to_one_per_paper_in_gaps(works_v2):
    """Fractional shares as ml/gaps.py computes them (its works_v2 fallback)."""
    for w in rows(works_v2):
        _, top = counts_from_works([w])
        if w["countries"] and w["topics"]:
            for t in set(w["topics"]):
                assert sum(v for _, v in top[t]) == pytest.approx(1.0, abs=1e-3)


def test_country_stats_tolerates_missing_topic_names():
    """OpenAlex topics without display_name must not leak None into top_topics."""
    w = normalize({"id": "https://openalex.org/W9", "display_name": "x", "publication_year": 2024,
                   "topics": [{"display_name": None}, {"display_name": "AI"}],
                   "authorships": [{"author": {"display_name": "A"}, "countries": ["PK"]}]})
    assert None not in w["topics"]
    for counting in ("fractional", "full"):
        for s in cs.to_stats(cs.tally([w]), counting=counting):
            CountryStats.model_validate(s)


def test_incremental_country_stats_equals_full_rebuild(tmp_path, raw_batches):
    p = tmp_path / "w.jsonl"
    b1, b2 = raw_batches
    ingest(p, b1)
    n_before = len(rows(p))
    ingest(p, b2)
    new = rows(p)[n_before:]
    prev = json.loads(json.dumps(cs.tally(rows(p)[:n_before])))  # round-trip like the snapshot
    inc = cs.to_stats(cs.combine(prev, cs.tally(new)))
    full = cs.to_stats(cs.tally(rows(p)))
    assert inc == full


# ---------- incremental == full rebuild for ml/ ----------

def test_incremental_patterns_equal_full_rebuild(tmp_path, raw_batches):
    b1, b2 = raw_batches
    inc_path, full_path = tmp_path / "inc.jsonl", tmp_path / "full.jsonl"
    kw = dict(min_support=0.1, min_baskets=1)
    inc = IncrementalMiner(tmp_path / "inc", **kw)
    ingest(inc_path, b1)
    inc.update([p.to_dict() for p in read_works(inc_path)], run_date="2026-10-01")
    ingest(inc_path, b2)
    s2 = inc.update([p.to_dict() for p in read_works(inc_path)], run_date="2026-10-15")
    assert s2["new_papers"] == 3  # already-seen works skipped

    ingest(full_path, b1 + b2)
    full = IncrementalMiner(tmp_path / "full", **kw)
    full.update([p.to_dict() for p in read_works(full_path)], run_date="2026-10-15")

    assert rows(inc_path) == rows(full_path)
    strip = lambda ps: [{k: v for k, v in r.items()} for r in ps]
    assert strip(inc.patterns()) == strip(full.patterns())
    # reload from disk gives the same state
    assert IncrementalMiner(tmp_path / "inc", **kw).patterns() == inc.patterns()


def test_incremental_index_equals_full_rebuild(tmp_path, raw_batches):
    b1, b2 = raw_batches
    p = tmp_path / "w.jsonl"
    a = MLService(embedder=HashEmbedder(), store=LocalStore(tmp_path / "a"),
                  cache=SummaryCache(tmp_path / "a.sqlite"))
    ingest(p, b1)
    a.index_papers(list(read_works(p)))
    ingest(p, b2)
    a.index_papers(list(read_works(p)))  # re-upsert all, as ml.cli index does
    b = MLService(embedder=HashEmbedder(), store=LocalStore(tmp_path / "b"),
                  cache=SummaryCache(tmp_path / "b.sqlite"))
    b.index_papers(list(read_works(p)))
    assert len(a.store) == len(b.store) == 8
    for q in ("protein folding", "quantum error correction", "satellite crops"):
        assert [h["work_id"] for h in a.search(q, k=5)] == [h["work_id"] for h in b.search(q, k=5)]


# ---------- API routes over pipeline output ----------

@pytest.fixture
def client(tmp_path, monkeypatch, works_v2):
    papers = list(read_works(works_v2))
    svc = MLService(embedder=HashEmbedder(), store=LocalStore(tmp_path / "v"),
                    cache=SummaryCache(tmp_path / "s.sqlite"))
    svc.index_papers(papers)
    miner = IncrementalMiner(tmp_path / "p", min_support=0.1, min_baskets=1)
    miner.update([p.to_dict() for p in papers], run_date="2026-10-15")
    monkeypatch.setattr(ml_bridge, "get_service", lambda: svc)
    monkeypatch.setattr(ml_bridge, "get_miner", lambda: miner)
    return TestClient(app)


def test_api_search_validates(client):
    r = client.get("/api/v1/search", params={"q": "protein folding", "limit": 3})
    assert r.status_code == 200
    body = SearchResponse.model_validate(r.json())
    assert 0 < len(body.results) <= 3
    r = client.get("/api/v1/search", params={"q": "protein", "country": "gb"}).json()
    assert [x["id"] for x in r["results"]] == ["W6"]


def test_api_paper_detail_validates(client):
    r = client.get("/api/v1/papers/W1")
    assert r.status_code == 200
    d = PaperDetail.model_validate(r.json())
    assert str(d.original_url) == "https://example.org/w1.pdf"
    assert str(d.openalex_url) == "https://openalex.org/W1"
    assert d.countries == ["CA", "PK"] and d.year == 2021
    assert client.get("/api/v1/papers/W404").status_code == 404


def test_api_ask_validates(client):
    r = client.post("/api/v1/papers/W1/ask", json={"question": "What model is used?"})
    assert r.status_code == 200
    a = AskResponse.model_validate(r.json())
    assert a.answer
    assert client.post("/api/v1/papers/W404/ask", json={"question": "x"}).status_code == 404


def test_api_related_validates(client):
    r = client.get("/api/v1/papers/W1/related", params={"limit": 3})
    assert r.status_code == 200
    items = [PaperSummary.model_validate(x) for x in r.json()]
    assert items and all(i.id != "W1" for i in items)


def test_api_patterns_validates(client):
    r = client.get("/api/v1/patterns")
    assert r.status_code == 200
    ps = [Pattern.model_validate(x) for x in r.json()]
    assert ps and all(p.window_end >= p.window_start and 0 < p.support <= 1 for p in ps)
    assert any(p.items == ["Deep Learning", "Protein Folding"] for p in ps)


def test_api_runs_validates(client):
    r = client.get("/api/v1/runs")
    assert r.status_code == 200
    runs = [Run.model_validate(x) for x in r.json()]
    assert len(runs) == 1 and runs[0].papers_added == 8 and runs[0].status == "success"


@pytest.fixture
def country_snapshot(tmp_path, monkeypatch, works_v2):
    out = tmp_path / "country_snapshot.json"
    cs.main(["--new", str(works_v2), "--out", str(out)])
    from pipeline import country_api
    monkeypatch.setattr(country_api, "SNAPSHOT", out)  # module reads the env var at import time
    monkeypatch.setenv("COUNTRY_SNAPSHOT", str(out))
    return json.loads(out.read_text())


@pytest.mark.parametrize("counting", COUNTINGS)
def test_country_api_helpers_validate(country_snapshot, counting):
    from pipeline import country_api
    if True:
        rs = country_api.countries(counting)
        assert rs and all(CountryStats.model_validate(r).counting == counting for r in rs)
    assert country_api.country("pk")["code"] == "PK"
    for c in country_api.collaborations():
        Collaboration.model_validate(c)


@pytest.mark.parametrize("counting", ["fractional", "full"])
def test_api_countries_by_counting(client, country_snapshot, counting):
    r = client.get("/api/v1/countries", params={"counting": counting})
    assert r.status_code == 200
    stats = [CountryStats.model_validate(x) for x in r.json()]
    assert stats and all(s.counting == counting for s in stats)
    full = {s["code"]: s["papers"] for s in country_snapshot["countries_full"]}
    if counting == "full":
        assert {s.code: s.papers for s in stats} == full


def test_api_countries_rejects_unknown_counting(client):
    assert client.get("/api/v1/countries", params={"counting": "bogus"}).status_code == 422


def test_api_country_detail(client, country_snapshot):
    r = client.get("/api/v1/countries/PK")
    assert r.status_code == 200
    assert CountryStats.model_validate(r.json()).code == "PK"


def test_api_collaborations_shape(client):
    r = client.get("/api/v1/countries/collaborations", params={"counting": "full"})
    assert r.status_code == 200
    for x in r.json():
        Collaboration.model_validate(x)


def test_api_collaborations_served_from_snapshot(client, country_snapshot):
    r = client.get("/api/v1/countries/collaborations", params={"counting": "full"})
    got = [Collaboration.model_validate(x) for x in r.json()]
    assert got and {(c.source, c.target) for c in got} >= {("CA", "PK"), ("CN", "PK")}


def test_collaborations_fractional_counting_supported():
    import inspect
    from pipeline import country_api
    assert "counting" in inspect.signature(country_api.collaborations).parameters


# ---------- gap finder: topic_year_counts contract ----------

def _gap_fixture():
    tyc = {"Hot Topic": {"2021": 4, "2022": 8, "2023": 16, "2024": 30, "2025": 50},
           "Big Topic": {"2021": 400, "2022": 410, "2023": 420, "2024": 430, "2025": 440},
           "Mid Topic": {"2021": 20, "2022": 24, "2023": 30, "2024": 36, "2025": 42}}
    top = {"Hot Topic": [["PK", 20.5], ["CA", 10.0]], "Big Topic": [["US", 300.0]],
           "Mid Topic": [["DE", 12.0]]}
    return tyc, top


def test_topic_year_counts_shape_from_works(works_v2):
    tyc, top = counts_from_works(read_works(works_v2))
    for topic, by_year in tyc.items():
        assert isinstance(topic, str)
        assert all(isinstance(int(y), int) and isinstance(n, int) and n > 0
                   for y, n in by_year.items())
    for topic, pairs in top.items():
        vals = [v for _, v in pairs]
        assert vals == sorted(vals, reverse=True)
        assert all(isinstance(c, str) and len(c) == 2 for c, _ in pairs)
    assert tyc["Protein Folding"] == {2021: 1, 2022: 1, 2024: 1}


def test_api_gap_patterns_from_snapshot(client, tmp_path, monkeypatch):
    tyc, top = _gap_fixture()
    snap = tmp_path / "country_snapshot.json"
    snap.write_text(json.dumps({"topic_year_counts": tyc, "topic_top_countries": top}))
    monkeypatch.setenv("COUNTRY_SNAPSHOT", str(snap))
    # find_gaps defaults last_year to the last complete calendar year; pin it via the snapshot data
    import ml.gaps as g
    real = g.find_gaps
    monkeypatch.setattr(ml_bridge, "find_gaps", lambda t, tp, **kw: real(t, tp, last_year=2025, **kw))
    r = client.get("/api/v1/patterns", params={"trend": "gap"})
    assert r.status_code == 200, r.text
    ps = [Pattern.model_validate(x) for x in r.json()]
    assert ps and ps[0].items == ["Hot Topic"] and ps[0].top_countries == ["PK", "CA"]
    assert all(p.gap_score is not None and p.support == p.gap_score for p in ps)
    assert load_inputs(snap)[2] == "snapshot"


def test_country_snapshot_has_gap_inputs(tmp_path, works_v2):
    out = tmp_path / "snap.json"
    cs.main(["--new", str(works_v2), "--out", str(out)])
    snap = json.loads(out.read_text())
    tyc, top = snap["topic_year_counts"], snap["topic_top_countries"]
    assert tyc and top
    for topic, by_year in tyc.items():
        assert all(str(y).isdigit() and isinstance(n, int) for y, n in by_year.items())
    assert load_inputs(out)[2] == "snapshot"
    assert find_gaps(tyc, top, last_year=2025, min_total=1, min_last=0) is not None
    # same yearly counts as ml/gaps.py's own fallback over works_v2.jsonl
    mine, _ = counts_from_works(read_works(works_v2))
    assert {t: {int(y): n for y, n in v.items()} for t, v in tyc.items()} == mine


def test_topic_top_countries_are_fractional_pairs(tmp_path, works_v2):
    out = tmp_path / "snap.json"
    cs.main(["--new", str(works_v2), "--out", str(out)])
    top = json.loads(out.read_text())["topic_top_countries"]
    _, expected = counts_from_works(read_works(works_v2))
    for t, pairs in top.items():
        assert all(isinstance(p, list) and len(p) == 2 for p in pairs)
        assert [c for c, _ in pairs] == [c for c, _ in expected[t]][:len(pairs)]


# ---------- collaboration pair weights (#3) ----------

def _pair_weights(w):
    t = cs.tally([w])
    return ({k: v for k, v in t["pairs_frac"].get("all", {}).items()},
            {k: v for k, v in t["pairs_1n"].get("all", {}).items()},
            dict(t["pairs"]))


@pytest.mark.parametrize("countries", [["PK"], ["CA", "PK"], ["CA", "PK", "US"],
                                       ["CA", "CN", "DE", "PK", "US"]])
def test_pair_weights_per_paper(countries):
    w = {"id": "W1", "year": 2024, "countries": countries, "topics": ["AI"]}
    frac, one_n, full = _pair_weights(w)
    n = len(countries)
    if n == 1:
        assert frac == one_n == full == {}
        return
    assert len(frac) == len(one_n) == len(full) == n * (n - 1) // 2
    assert sum(frac.values()) == pytest.approx(1.0)
    assert sum(one_n.values()) == pytest.approx((n - 1) / 2)
    assert all(v == 1 for v in full.values())


def test_pair_weights_over_corpus(works_v2):
    works = rows(works_v2)
    t = cs.tally(works)
    multi = [w for w in works if len(w["countries"]) > 1]
    assert sum(t["pairs_frac"]["all"].values()) == pytest.approx(len(multi))
    assert sum(t["pairs_1n"]["all"].values()) == pytest.approx(
        sum((len(w["countries"]) - 1) / 2 for w in multi))
    assert sum(t["pairs"].values()) == sum(len(w["countries"]) * (len(w["countries"]) - 1) // 2
                                           for w in works)


def test_incremental_pair_weights_equal_full(raw_batches, tmp_path):
    p = tmp_path / "w.jsonl"
    b1, b2 = raw_batches
    ingest(p, b1); n = len(rows(p)); ingest(p, b2)
    prev = json.loads(json.dumps(cs.tally(rows(p)[:n])))
    inc, full = cs.combine(prev, cs.tally(rows(p)[n:])), cs.tally(rows(p))
    for k in ("pairs_frac", "pairs_1n"):
        assert dict(inc[k]["all"]) == pytest.approx(dict(full[k]["all"]))
    assert dict(inc["pairs"]) == dict(full["pairs"])




@pytest.mark.parametrize("counting", ["fractional", "full", "per_country"])
def test_api_collaborations_by_counting(client, country_snapshot, counting):
    r = client.get("/api/v1/countries/collaborations", params={"counting": counting})
    assert r.status_code == 200, r.text
    got = [Collaboration.model_validate(x) for x in r.json()]
    key = {"full": "collaborations_full", "per_country": "collaborations_1n"}.get(
        counting, "collaborations")
    assert [c.model_dump() for c in got] == country_snapshot[key]


def test_api_collaborations_limit_respected(client, country_snapshot):
    r = client.get("/api/v1/countries/collaborations", params={"counting": "fractional", "limit": 2})
    assert r.status_code == 200 and len(r.json()) == 2
