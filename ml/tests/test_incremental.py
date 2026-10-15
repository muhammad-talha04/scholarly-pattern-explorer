import random

import numpy as np

from fpgrowth import frequent_itemsets
from ml.embeddings import HashEmbedder
from ml.incremental import IncrementalMiner, assign_topics

TOPICS = ["ML", "NLP", "Vision", "Genomics", "Quantum", "Climate"]


def make(n, start=0, seed=0):
    rng = random.Random(seed)
    return [{"work_id": f"W{start + i}", "pub_year": rng.randint(2015, 2020),
             "topics": rng.sample(TOPICS, rng.randint(2, 4))} for i in range(n)]


def batch_patterns(papers, y0, y1, ms=0.1):
    baskets = [p["topics"] for p in papers if y0 <= p["pub_year"] <= y1]
    sets, n = frequent_itemsets(baskets, min_support=ms, max_len=3)
    return {" | ".join(sorted(s)): c for s, c in sets.items()}


def test_incremental_equals_full_recompute(tmp_path):
    old, new = make(300, 0, 1), make(120, 300, 2)
    m = IncrementalMiner(tmp_path, min_support=0.1)
    m.update(old, run_date="2026-10-01")
    s = IncrementalMiner(tmp_path, min_support=0.1).update(old + new, run_date="2026-10-08")  # reload + dupes
    assert s["new_papers"] == 120
    m2 = IncrementalMiner(tmp_path, min_support=0.1)
    for win in m2.state["windows"].values():
        got = {p["itemset"]: p["support_count"] for p in win["patterns"]}
        assert got == batch_patterns(old + new, win["window_start"], win["window_end"])


def test_only_touched_windows_update_and_snapshots(tmp_path):
    m = IncrementalMiner(tmp_path, min_support=0.1)
    m.update(make(200, 0, 3), run_date="2026-10-01")
    s = m.update([{"work_id": "N1", "pub_year": 2030, "topics": ["ML", "NLP"]}], run_date="2026-10-02")
    assert s["windows_updated"] == [2028, 2029, 2030]
    assert m.update(make(200, 0, 3), run_date="2026-10-03")["new_papers"] == 0
    tl = m.timeline()
    assert [t["date"] for t in tl] == ["2026-10-01", "2026-10-02", "2026-10-03"]
    assert tl[0]["total_papers"] == 200 and tl[1]["total_papers"] == 201


def test_assign_topics_to_existing():
    emb = HashEmbedder()
    cents = {"Quantum": emb.encode(["quantum qubits"])[0], "Climate": emb.encode(["climate warming"])[0]}
    papers = [{"work_id": "X", "title": "qubits quantum", "abstract": "", "topics": []}]
    assign_topics(papers, cents, emb, k=1, min_sim=0.1)
    assert papers[0]["topics"] == ["Quantum"] and papers[0]["topics_assigned"]
