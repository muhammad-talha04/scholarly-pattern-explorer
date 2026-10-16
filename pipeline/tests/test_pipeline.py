import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pipeline.ingest import abstract_from_index, normalize, merge
from pipeline.country_stats import (TOPIC_COUNTRY_YEAR_COLUMNS, combine, fractional_weights,
                                    snapshot, tally)

W = {"id": "https://openalex.org/W1", "display_name": "T", "publication_year": 2025,
     "doi": "https://doi.org/10.1/x", "abstract_inverted_index": {"hello": [0], "world": [1]},
     "open_access": {"oa_url": "https://x.org/p.pdf"},
     "authorships": [{"author": {"display_name": "A"}, "countries": ["PK"]},
                     {"author": {"display_name": "B"}, "institutions": [{"country_code": "CA"}]}],
     "topics": [{"display_name": None}, {"display_name": "AI"}]}


def test_abstract():
    assert abstract_from_index({"b": [1], "a": [0]}) == "a b"
    assert abstract_from_index(None) is None


def test_normalize():
    r = normalize(W)
    assert r["id"] == "W1" and r["abstract"] == "hello world" and r["topics"] == ["AI"]
    assert r["countries"] == ["CA", "PK"] and r["original_url"].endswith(".pdf")


def test_normalize_drops_placeholder_doi():
    fake = {**W, "doi": "https://doi.org/10.1234/spe.0",
            "open_access": {"oa_url": "https://doi.org/10.1234/spe.0"},
            "primary_location": {"landing_page_url": "https://doi.org/10.1234/spe.9"}}
    r = normalize(fake)
    assert r["doi"] is None and r["original_url"] is None
    kept = normalize({**W, "doi": "https://doi.org/10.1234/spe.0"})
    assert kept["doi"] is None and kept["original_url"].endswith(".pdf")


def test_merge_dedups(tmp_path):
    p = tmp_path / "w.jsonl"
    r = normalize(W)
    assert merge(p, [r, r]) == 1 and merge(p, [r]) == 0


def _two():
    a = normalize(W)
    return a, {**a, "id": "W2", "year": 2026, "countries": ["PK"]}


def test_incremental_matches_full_and_counting():
    a, b = _two()
    full = snapshot(tally([a, b]))
    inc = snapshot(combine(json.loads(json.dumps(tally([a]))), tally([b])))
    assert full["countries"] == inc["countries"] and full["topic_year_counts"] == inc["topic_year_counts"]
    assert full["topic_country_year"] == inc["topic_country_year"]
    pk = next(r for r in full["countries"] if r["code"] == "PK")
    assert pk["papers"] == 1.5 and pk["name"] == "Pakistan"
    # two papers are far below the 30-paper minimum: no growth figure
    assert pk["growth_pct"] is None and pk["growth_reason"] == "too_few_papers"
    pkf = next(r for r in full["countries_full"] if r["code"] == "PK")
    assert pkf["papers"] == 2 and pkf["growth_pct"] is None
    assert all(None not in r["top_topics"] for r in full["countries"])
    assert full["topic_year_counts"]["AI"] == {"2025": 1, "2026": 1}
    assert full["topic_top_countries"]["AI"][0] == ["PK", 1.5]
    assert full["collaborations"] == [{"source": "CA", "target": "PK", "papers": 1}]
    assert full["collaborations_1n"] == [{"source": "CA", "target": "PK", "papers": 0.5}]
    assert full["collaborations_full"] == [{"source": "CA", "target": "PK", "papers": 1}]


def test_partial_run_keeps_pages(tmp_path, monkeypatch):
    import pipeline.ingest as ing
    def fake(*a, **k):
        for i in range(250):
            yield {**normalize(W), "id": f"W{i}"}
        raise SystemExit("OpenAlex HTTP 401: set OPENALEX_API_KEY")
    monkeypatch.setattr(ing, "fetch", fake)
    out, st = tmp_path / "w.jsonl", tmp_path / "s.json"
    assert ing.main(["--out", str(out), "--state", str(st)]) == 1
    assert len(out.read_text().splitlines()) == 250 and not st.exists()


def test_country_api(tmp_path, monkeypatch):
    import pipeline.country_api as api
    p = tmp_path / "snap.json"
    p.write_text(json.dumps(snapshot(tally(list(_two())))))
    monkeypatch.setattr(api, "SNAPSHOT", p)
    pk = api.country("pk")
    assert pk["papers"] == 1.5 and pk["fractional_count"] == 1.5 and pk["paper_count"] == 2
    assert {y["year"]: (y["paper_count"], y["fractional_count"]) for y in pk["by_year"]} == {
        2025: (1, 0.5), 2026: (1, 1.0)}
    assert api.country("PK", "full")["papers"] == 2
    assert api.collaborations()[0]["papers"] == 1 and api.collaborations("per_country")[0]["papers"] == 0.5 and api.collaborations("full")[0]["papers"] == 1


def test_pair_weights_sum_to_one_per_paper():
    w = {**normalize(W), "countries": ["A", "B", "C", "D"]}
    t = tally([w])
    assert abs(sum(t["pairs_frac"]["all"].values()) - 1) < 1e-9
    assert abs(sum(t["pairs_1n"]["all"].values()) - 1.5) < 1e-9
    assert not tally([{**w, "countries": ["A"]}])["pairs"]


def test_fractional_edges():
    """No country, one country, and the same country on several authors."""
    assert fractional_weights([]) == {}
    assert fractional_weights([None, "", "  "]) == {}
    assert fractional_weights(["PK"]) == {"PK": 1.0}
    # duplicates across authors, and mixed case, are one country
    assert fractional_weights(["CA", "ca", "PK", "PK"]) == {"CA": 0.5, "PK": 0.5}
    assert abs(sum(fractional_weights(["CA", "US", "PK"]).values()) - 1) < 1e-9

    raw = {**W, "id": "https://openalex.org/W9", "publication_year": 2024,
           "authorships": [
               {"author": {"display_name": "A"}, "countries": ["CA"],
                "institutions": [{"country_code": "CA"}]},
               {"author": {"display_name": "B"}, "countries": ["CA", "CA"]},
               {"author": {"display_name": "C"}, "institutions": [{"country_code": "PK"}, {"country_code": "PK"}]},
           ],
           "topics": [{"id": "https://openalex.org/T1", "display_name": "AI"}]}
    paper = normalize(raw)
    assert paper["countries"] == ["CA", "PK"]
    assert paper["topic_refs"] == [{"id": "T1", "name": "AI"}]
    weights = fractional_weights(paper["countries"])
    assert abs(sum(weights.values()) - 1) < 1e-9 and weights["CA"] == 0.5

    none = {**normalize(W), "id": "W0", "countries": [], "year": 2024}
    one = {**normalize(W), "id": "W1", "countries": ["PK"], "year": 2024}
    assert fractional_weights(none["countries"]) == {}
    assert fractional_weights(one["countries"]) == {"PK": 1.0}
    # a list that still contains duplicate countries (not pre-deduped) counts N distinct
    dup_list = {**one, "id": "Wdup", "countries": ["CA", "CA", "PK"]}
    rows = { (r["topic_id"], r["country_code"]): r
             for r in snapshot(tally([dup_list]))["topic_country_year"] }
    assert rows[("AI", "CA")]["fractional_count"] == 0.5
    assert rows[("AI", "PK")]["fractional_count"] == 0.5
    assert rows[("AI", "CA")]["paper_count"] == 1
    assert snapshot(tally([none]))["topic_country_year"] == []
    only = snapshot(tally([one]))["topic_country_year"]
    assert only == [{"topic_id": "AI", "topic_name": "AI", "country_code": "PK",
                     "year": 2024, "paper_count": 1, "fractional_count": 1.0}]


def test_fractional_and_aggregate_match_raw():
    """Every paper's country shares sum to 1, and the aggregate matches a raw recount."""
    none = {**normalize(W), "id": "W0", "countries": [], "year": 2024}
    one = {**normalize(W), "id": "W1", "countries": ["PK"], "year": 2024}
    two = {**normalize(W), "id": "W2", "year": 2025, "countries": ["CA", "CA", "PK"],
           "topic_refs": [{"id": "T1", "name": "AI"}, {"id": "T2", "name": "Graphs"}]}
    works = [none, one, two]
    for w in works:
        weights = fractional_weights(w["countries"])
        if w["countries"] and fractional_weights(w["countries"]):
            assert abs(sum(weights.values()) - 1) < 1e-9
        else:
            assert weights == {}

    rows = snapshot(tally(works))["topic_country_year"]
    assert rows and set(rows[0]) == set(TOPIC_COUNTRY_YEAR_COLUMNS)

    expect_p, expect_f, names = {}, {}, {}
    for w in works:
        codes, seen = [], set()
        for c in w["countries"]:
            code = str(c).strip().upper()
            if code and code not in seen:
                seen.add(code)
                codes.append(code)
        if not codes:
            continue
        share = 1 / len(codes)
        for ref in w["topic_refs"]:
            names[ref["id"]] = ref["name"]
            for code in codes:
                key = (ref["id"], code, w["year"])
                expect_p[key] = expect_p.get(key, 0) + 1
                expect_f[key] = expect_f.get(key, 0) + share
    got = {(r["topic_id"], r["country_code"], r["year"]): r for r in rows}
    assert set(got) == set(expect_p)
    for key, row in got.items():
        assert row["paper_count"] == expect_p[key]
        assert abs(row["fractional_count"] - expect_f[key]) < 1e-9
        assert row["topic_name"] == names[key[0]]
    # fractional shares of T1 in 2025 are one paper split across two countries
    assert abs(sum(r["fractional_count"] for r in rows
                   if r["topic_id"] == "T1" and r["year"] == 2025) - 1) < 1e-9


def test_topic_country_year_updates_incrementally(tmp_path):
    import pipeline.country_stats as cs
    first = {**normalize(W), "id": "W1", "year": 2024, "countries": ["PK"]}
    second = {**normalize(W), "id": "W2", "year": 2024, "countries": ["PK", "CA"],
              "topic_refs": [{"id": "T9", "name": "Graphs"}]}
    new1, new2 = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    out, table = tmp_path / "snap.json", tmp_path / "topic_country_year.sqlite"
    new1.write_text(json.dumps(first) + "\n")
    new2.write_text(json.dumps(second) + "\n")
    assert cs.main(["--new", str(new1), "--out", str(out), "--table", str(table)]) is None
    cs.main(["--new", str(new2), "--prev", str(out), "--out", str(out), "--table", str(table)])
    import sqlite3
    con = sqlite3.connect(table)
    cols = [r[1] for r in con.execute("PRAGMA table_info(topic_country_year)")]
    assert cols == list(TOPIC_COUNTRY_YEAR_COLUMNS)
    view_cols = [r[1] for r in con.execute("PRAGMA table_info(topic_country_year_v)")]
    assert view_cols == cols
    stored = {(r[0], r[2], r[3]): (r[4], r[5]) for r in con.execute(
        "SELECT topic_id, topic_name, country_code, year, paper_count, fractional_count FROM topic_country_year_v")}
    # W1 is AI/PK/2024 whole 1. W2 adds Graphs for PK and CA, and does not double-count W1.
    assert stored[("AI", "PK", 2024)] == (1, 1.0)
    assert stored[("T9", "PK", 2024)][0] == 1 and stored[("T9", "CA", 2024)][0] == 1
    assert abs(stored[("T9", "PK", 2024)][1] + stored[("T9", "CA", 2024)][1] - 1) < 1e-9
    full = snapshot(tally([first, second]))["topic_country_year"]
    assert json.loads(out.read_text())["topic_country_year"] == full


def test_output_paths_anchor_to_repo_root(tmp_path, monkeypatch):
    from ml.paths import REPO_ROOT
    from pipeline.country_stats import output_paths
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TOPIC_COUNTRY_YEAR_DB", raising=False)
    out, table = output_paths("data/country_snapshot.json", None)
    assert out == REPO_ROOT / "data" / "country_snapshot.json"
    assert table == REPO_ROOT / "data" / "topic_country_year.sqlite"
    out_abs, table_abs = output_paths(str(tmp_path / "snap.json"), None)
    assert out_abs == tmp_path / "snap.json"
    assert table_abs == tmp_path / "topic_country_year.sqlite"
    monkeypatch.setenv("TOPIC_COUNTRY_YEAR_DB", "custom/t.sqlite")
    _, table_env = output_paths(str(tmp_path / "snap.json"), None)
    assert table_env == REPO_ROOT / "custom" / "t.sqlite"


def test_aggregate_seeds_once_from_corpus(tmp_path):
    """An older snapshot has no topic-country-year counters; the corpus fills them once."""
    import pipeline.country_stats as cs
    older = {**normalize(W), "id": "Wold", "year": 2023, "countries": ["CA"],
             "raw": {"topics": [{"id": "https://openalex.org/T7", "display_name": "Graphs"}]}}
    older.pop("topic_refs")  # legacy row: the id is only on raw.topics
    newer = {**normalize(W), "id": "Wnew", "year": 2024, "countries": ["PK"]}
    # legacy row: topics by name only, real id lives on raw
    assert snapshot(tally([older]))["topic_country_year"][0]["topic_id"] == "T7"
    prev = snapshot(tally([older]))
    del prev["tally"]["tcy_papers"]
    del prev["tally"]["tcy_frac"]
    del prev["tally"]["topic_names"]
    corpus, newp, out = tmp_path / "all.jsonl", tmp_path / "new.jsonl", tmp_path / "snap.json"
    prev_path = tmp_path / "prev.json"
    corpus.write_text(json.dumps(older) + "\n" + json.dumps(newer) + "\n")
    newp.write_text(json.dumps(newer) + "\n")
    prev_path.write_text(json.dumps(prev))
    cs.main(["--new", str(newp), "--prev", str(prev_path), "--corpus", str(corpus),
             "--out", str(out), "--table", str(tmp_path / "t.sqlite")])
    rows = {(r["topic_id"], r["country_code"], r["year"]): r["paper_count"]
            for r in json.loads(out.read_text())["topic_country_year"]}
    assert rows[("T7", "CA", 2023)] == 1
    assert rows[("AI", "PK", 2024)] == 1
    # country counters were not rebuilt from the corpus: PK is only the new paper, CA stays 1
    codes = {r["code"]: r["papers"] for r in json.loads(out.read_text())["countries_full"]}
    assert codes["CA"] == 1 and codes["PK"] == 1
    # a later run must keep adding; a stale --corpus must not rebuild the aggregate
    third = {**normalize(W), "id": "W3", "year": 2025, "countries": ["US"]}
    new3 = tmp_path / "new3.jsonl"
    new3.write_text(json.dumps(third) + "\n")
    stale = tmp_path / "stale.jsonl"
    stale.write_text(json.dumps(older) + "\n")
    cs.main(["--new", str(new3), "--prev", str(out), "--corpus", str(stale),
             "--out", str(out), "--table", str(tmp_path / "t.sqlite")])
    rows = {(r["topic_id"], r["country_code"], r["year"]): r["paper_count"]
            for r in json.loads(out.read_text())["topic_country_year"]}
    assert rows[("T7", "CA", 2023)] == 1 and rows[("AI", "PK", 2024)] == 1
    assert rows[("AI", "US", 2025)] == 1
