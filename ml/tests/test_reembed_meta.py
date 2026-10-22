"""publication_date (and other meta keys) must survive export -> index --reembed."""
import numpy as np

from ml.embeddings import HashEmbedder
from ml.export_corpus import export, meta_to_v2
from ml.indexer import index
from ml.papers import Paper, read_works
from ml.store import LocalStore


def _meta(wid, **kw):
    return {**Paper(wid, f"T {wid}", f"Abstract for {wid} about surface codes.", pub_year=2020,
                    created="2024-11-02").to_dict(), **kw}


def test_publication_date_survives_reembed_round_trip(tmp_path):
    store = LocalStore(tmp_path / "vec")
    metas = [_meta("W1", publication_date="2017-03-04", lang="en"),
             _meta("W2", publication_date=None),          # looked up, unknown
             _meta("W3")]                                 # never backfilled
    store.upsert(["W1", "W2", "W3"], np.ones((3, 384), dtype=np.float32) / np.sqrt(384), metas, model="old")
    out = tmp_path / "works_live.jsonl"
    assert export(store, out) == 3

    res = index(store, list(read_works(out)), batch_size=2, reembed=True, embedder=HashEmbedder())
    assert res.embedded == 3

    after = LocalStore(tmp_path / "vec")
    w1, w2, w3 = after.get("W1"), after.get("W2"), after.get("W3")
    assert w1["publication_date"] == "2017-03-04" and w1["lang"] == "en"
    assert "publication_date" in w2 and w2["publication_date"] is None
    assert "publication_date" not in w3
    assert after.ids_missing_publication_date() == ["W3"]
    assert after.month_counts() == {"2017-03": 1, "2024-11": 2}
    for wid, before in zip(["W1", "W2", "W3"], metas):   # nothing else dropped or changed
        assert after.get(wid) == before
    assert set(after.models.values()) != {"old"}


def test_meta_to_v2_keeps_key_presence():
    assert "publication_date" not in meta_to_v2(_meta("W9"))
    row = meta_to_v2(_meta("W9", publication_date=None, extra_key=1))
    assert row["publication_date"] is None and row["meta_extra"] == {"extra_key": 1}
    assert Paper.from_record(row).to_dict()["publication_date"] is None
