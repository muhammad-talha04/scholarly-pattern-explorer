import json

from spe_pipeline.openalex import build_filters, parser
from spe_pipeline.parse import parse_work, reconstruct_abstract, short_id
from spe_pipeline.windows import MiningParams, all_windows, dirty_windows

REC = {
    "id": "https://openalex.org/W1", "doi": "https://doi.org/10.1/x",
    "display_name": "A paper", "publication_year": 2021, "cited_by_count": 4,
    "abstract_inverted_index": {"hello": [0], "world": [1, 3], "big": [2]},
    "topics": [
        {"id": "https://openalex.org/T1", "display_name": "ML", "score": 0.9,
         "field": {"display_name": "CS"}},
        {"id": "https://openalex.org/T1", "display_name": "ML dup"},
        {"id": "https://openalex.org/T2", "display_name": "NLP", "score": 0.5},
    ],
    "authorships": [
        {"author": {"id": "https://openalex.org/A1", "display_name": "X"},
         "institutions": [{"display_name": "U", "country_code": "pk"}], "countries": ["CA"]},
        {"author": {}, "institutions": [{"country_code": "US"}]},
    ],
    "open_access": {"oa_url": "https://oa"},
}


def test_short_id_and_abstract():
    assert short_id("https://openalex.org/W9") == "W9"
    assert short_id(None) is None
    assert reconstruct_abstract(REC["abstract_inverted_index"]) == "hello world big world"
    assert reconstruct_abstract(None) is None


def test_parse_work():
    pw = parse_work(json.loads(json.dumps(REC)))
    assert pw.work["work_id"] == "W1" and pw.work["oa_url"] == "https://oa"
    assert [t["topic_id"] for t in pw.topics] == ["T1", "T2"]
    assert pw.countries == {"PK", "CA", "US"}
    assert [a["author_id"] for a in pw.authors] == ["A1"]
    assert pw.authors[0]["country"] == "PK"
    assert parse_work({"id": "x"}) is None


def test_windows():
    assert all_windows(2000, 2004, 3, 1) == [(2000, 2002), (2001, 2003), (2002, 2004)]
    assert dirty_windows([2004], 2000, 2004, 3, 1) == [(2002, 2004)]
    assert dirty_windows([2001], 2000, 2004, 3, 1) == [(2000, 2002), (2001, 2003)]
    assert dirty_windows([], 2000, 2004, 3, 1) == []


def test_params_hash_stable():
    assert MiningParams().hash() == MiningParams().hash()
    assert MiningParams(min_support=0.01).hash() != MiningParams().hash()


def test_filters():
    a = parser().parse_args(["--subfield-id", "1702", "--min-cited", "10",
                             "--from-updated", "2026-10-01"])
    f = build_filters(a)
    assert "primary_topic.subfield.id:subfields/1702" in f
    assert "cited_by_count:>9" in f and "from_updated_date:2026-10-01" in f
