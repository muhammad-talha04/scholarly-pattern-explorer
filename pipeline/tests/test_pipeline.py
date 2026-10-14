import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pipeline.ingest import abstract_from_index, normalize, merge
from pipeline.country_stats import tally, combine, to_stats

W = {"id": "https://openalex.org/W1", "display_name": "T", "publication_year": 2025,
     "doi": "https://doi.org/10.1/x", "abstract_inverted_index": {"hello": [0], "world": [1]},
     "open_access": {"oa_url": "https://x.org/p.pdf"},
     "authorships": [{"author": {"display_name": "A"}, "countries": ["PK"]},
                     {"author": {"display_name": "B"}, "countries": ["CA", "PK"]}],
     "topics": [{"display_name": "AI"}]}

def test_abstract():
    assert abstract_from_index({"b": [1], "a": [0]}) == "a b"
    assert abstract_from_index(None) is None

def test_normalize():
    r = normalize(W)
    assert r["id"] == "W1" and r["abstract"] == "hello world"
    assert r["countries"] == ["CA", "PK"] and r["original_url"].endswith(".pdf")

def test_merge_dedups(tmp_path):
    p = tmp_path / "w.jsonl"
    r = normalize(W)
    assert merge(p, [r, r]) == 1 and merge(p, [r]) == 0

def test_incremental_matches_full():
    a, b = normalize(W), {**normalize(W), "id": "W2", "year": 2026, "countries": ["PK"]}
    full = to_stats(tally([a, b]))
    inc = to_stats(combine(json.loads(json.dumps(tally([a]))), tally([b])))
    assert full == inc
    pk = next(r for r in full if r["code"] == "PK")
    assert pk["papers"] == 2 and pk["growth_pct"] == 0.0 and pk["name"] == "Pakistan"
