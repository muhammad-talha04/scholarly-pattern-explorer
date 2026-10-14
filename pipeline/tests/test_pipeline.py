import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pipeline.ingest import abstract_from_index, normalize, merge
from pipeline.country_stats import tally, combine, to_stats, snapshot

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
    pk = next(r for r in full["countries"] if r["code"] == "PK")
    assert pk["papers"] == 1.5 and pk["growth_pct"] == 100.0 and pk["name"] == "Pakistan"
    pkf = next(r for r in full["countries_full"] if r["code"] == "PK")
    assert pkf["papers"] == 2 and pkf["growth_pct"] == 0.0
    assert all(None not in r["top_topics"] for r in full["countries"])
    assert full["topic_year_counts"]["AI"] == {"2025": 1, "2026": 1}
    assert full["topic_top_countries"]["AI"][0] == ["PK", 1.5]
    assert full["collaborations"] == [{"source": "CA", "target": "PK", "papers": 0.5}]
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
    assert api.country("pk")["papers"] == 1.5
    assert api.country("PK", "full")["papers"] == 2
    assert api.collaborations()[0]["papers"] == 0.5 and api.collaborations("full")[0]["papers"] == 1
