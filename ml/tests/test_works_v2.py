import json

from ml.papers import Paper, default_works_path, read_works


def test_reads_v2_and_prefers_it(tmp_path, monkeypatch):
    monkeypatch.delenv("ML_WORKS_PATH", raising=False)
    (tmp_path / "data").mkdir()
    old = {"id": "https://openalex.org/W7", "title": "Old", "publication_year": 2019,
           "abstract_inverted_index": {"old": [0]}}
    (tmp_path / "data/works.jsonl").write_text(json.dumps(old) + "\n")
    assert default_works_path(tmp_path).name == "works.jsonl"          # fallback
    assert [p.work_id for p in read_works(tmp_path / "data/works.jsonl")] == ["W7"]
    v2 = {"id": "W8", "title": "New", "year": 2025, "abstract": "a b", "doi": None,
          "original_url": "https://x.org/p.pdf", "openalex_url": "https://openalex.org/W8",
          "authors": ["A", None], "countries": ["PK"], "topics": ["AI", "ML"], "cited_by": 3,
          "raw": {}}
    (tmp_path / "data/works_v2.jsonl").write_text(json.dumps(v2) + "\n")
    assert default_works_path(tmp_path).name == "works_v2.jsonl"       # preferred
    p = list(read_works(tmp_path / "data/works_v2.jsonl"))[0]
    assert (p.work_id, p.pub_year, p.authors, p.countries, p.cited_by) == ("W8", 2025, ["A"], ["PK"], 3)
    assert p.best_original_url == "https://x.org/p.pdf"
    assert Paper.from_record(old).abstract == "old"
