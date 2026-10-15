"""Compare incremental topic assignment and pattern mining with a full rebuild.

Two checks on one sample:

1. Patterns. Papers that already have topics are mined in batches with
   ml.incremental.IncrementalMiner, then again in one shot. The basket
   multiset is the same, so itemsets and supports should match. This is the
   pattern half of "incremental versus full rebuild".

2. Topics. Papers with no topics are labelled from topic centroids.
   The full rebuild builds centroids from every labelled paper, then assigns
   the rest once. The incremental run walks papers in year order and updates
   centroids as it goes, so a topic can drift and a single full-rebuild topic
   can split across two incremental labels. Drift is 1 minus the mean Jaccard
   of the assigned topic sets. A split is a full-rebuild topic whose papers
   received two or more different incremental labels.

    python eval/pattern_stability.py
    python eval/pattern_stability.py --works data/works_v2.jsonl

Relative --works paths are resolved from the repo root (ml.paths).
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.incremental import IncrementalMiner, assign_topics  # noqa: E402
from ml.paths import resolve  # noqa: E402

MINER = dict(window=3, step=1, min_support=0.1, max_len=3, min_confidence=0.5, min_baskets=10)


def _text(p: dict) -> str:
    return f"{p.get('title', '')}. {p.get('abstract', '')}".strip()


def _accumulate(sums, counts, topics, vec):
    for topic in topics:
        if topic not in sums:
            sums[topic] = np.zeros_like(vec, dtype=np.float64)
            counts[topic] = 0
        sums[topic] = sums[topic] + vec
        counts[topic] += 1


def _means(sums, counts) -> dict:
    return {t: (sums[t] / counts[t]).astype(np.float32) for t in sums}


def assign_incremental(papers: list[dict], embedder, k: int = 1, min_sim: float = 0.3) -> list[dict]:
    """Label topic-less papers in year order, folding each assignment into the centroids."""
    ordered = sorted((dict(p) for p in papers), key=lambda p: (p.get("pub_year") or 0, p["work_id"]))
    sums, counts = {}, {}
    out = []
    for p in ordered:
        topics = list(p.get("topics") or [])
        vec = embedder.encode([_text(p)])[0]
        if topics:
            _accumulate(sums, counts, topics, vec)
        else:
            cents = _means(sums, counts)
            if cents:
                assign_topics([p], cents, embedder, k=k, min_sim=min_sim)
                if p.get("topics"):
                    _accumulate(sums, counts, p["topics"], vec)
        out.append(p)
    return out


def assign_full(papers: list[dict], embedder, k: int = 1, min_sim: float = 0.3) -> list[dict]:
    """Label every topic-less paper from centroids of all labelled papers."""
    copied = [dict(p) for p in papers]
    labeled = [p for p in copied if p.get("topics")]
    sums, counts = {}, {}
    if labeled:
        vecs = embedder.encode([_text(p) for p in labeled])
        for p, vec in zip(labeled, vecs):
            _accumulate(sums, counts, p["topics"], vec)
    cents = _means(sums, counts)
    unlabeled = [p for p in copied if not p.get("topics")]
    if unlabeled and cents:
        assign_topics(unlabeled, cents, embedder, k=k, min_sim=min_sim)
    return copied


def mine_batches(papers: list[dict], batch: int, **cfg) -> list[dict]:
    dest = Path(tempfile.mkdtemp(prefix="patterns-inc-"))
    miner = IncrementalMiner(dest, **cfg)
    ordered = sorted(papers, key=lambda p: (p.get("pub_year") or 0, p["work_id"]))
    step = max(1, batch)
    for i in range(0, len(ordered), step):
        miner.update(ordered[i:i + step], run_date="2026-10-15")
    return miner.patterns()


def mine_once(papers: list[dict], **cfg) -> list[dict]:
    dest = Path(tempfile.mkdtemp(prefix="patterns-full-"))
    miner = IncrementalMiner(dest, **cfg)
    miner.update(list(papers), run_date="2026-10-15")
    return miner.patterns()


def _key(row: dict):
    return (row["window_start"], row["itemset"])


def compare_patterns(incremental_rows: list[dict], full_rows: list[dict]) -> dict:
    inc = {_key(r): r["support"] for r in incremental_rows}
    full = {_key(r): r["support"] for r in full_rows}
    keys_i, keys_f = set(inc), set(full)
    if not keys_i and not keys_f:
        jaccard, mae = 1.0, 0.0
    else:
        jaccard = len(keys_i & keys_f) / len(keys_i | keys_f)
        shared = keys_i & keys_f
        mae = (sum(abs(inc[k] - full[k]) for k in shared) / len(shared)) if shared else None
    return {
        "pattern_jaccard": round(jaccard, 4),
        "support_mae": None if mae is None else round(mae, 6),
        "patterns_incremental": len(keys_i),
        "patterns_full": len(keys_f),
        "patterns_only_incremental": len(keys_i - keys_f),
        "patterns_only_full": len(keys_f - keys_i),
    }


def _jaccard(a, b) -> float:
    a, b = set(a or []), set(b or [])
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def topic_drift_and_splits(original: list[dict], incremental: list[dict], full: list[dict]) -> dict:
    inc = {p["work_id"]: p for p in incremental}
    rebuilt = {p["work_id"]: p for p in full}
    unlabeled = [p["work_id"] for p in original if not (p.get("topics") or [])]
    scores = []
    disagreed = 0
    groups: dict[str, Counter] = {}
    for wid in unlabeled:
        a = inc[wid].get("topics") or []
        b = rebuilt[wid].get("topics") or []
        scores.append(_jaccard(a, b))
        if set(a) != set(b):
            disagreed += 1
        full_topic = b[0] if b else None
        inc_topic = a[0] if a else None
        if full_topic is not None:
            groups.setdefault(full_topic, Counter())[inc_topic] += 1
    mean_j = sum(scores) / len(scores) if scores else 1.0
    splits = []
    for topic, counts in sorted(groups.items()):
        labels = {str(t): n for t, n in counts.items() if t is not None}
        if len(labels) >= 2 and sum(labels.values()) >= 2:
            splits.append({"full_topic": topic, "incremental_topics": dict(sorted(labels.items()))})
    return {
        "unlabeled": len(unlabeled),
        "topic_jaccard": round(mean_j, 4),
        "topic_drift": round(1 - mean_j, 4),
        "papers_disagreed": disagreed,
        "topic_split_count": len(splits),
        "topic_splits": splits,
    }


def fixed_topic_sample(n: int = 80, seed: int = 0) -> list[dict]:
    import random
    rng = random.Random(seed)
    topics = ["ML", "NLP", "Vision", "Quantum"]
    papers = []
    for i in range(n):
        papers.append({
            "work_id": f"F{i}",
            "pub_year": rng.randint(2016, 2021),
            "title": f"fixed {i}",
            "abstract": "",
            "topics": rng.sample(topics, rng.randint(2, 3)),
        })
    return papers


class _DriftEmbedder:
    """Two unlabelled papers sit between Alpha and Beta; a third sits on Beta.

    Before Beta's seed arrives, the in-between papers are nearest to Alpha.
    A full rebuild sees both seeds and assigns all three to Beta. After Beta
    arrives, the paper that sits on Beta stays with Beta, so Beta splits.
    """

    def encode(self, texts: list[str]) -> np.ndarray:
        rows = []
        for text in texts:
            if "seed-a" in text:
                rows.append([1.0, 0.0])
            elif "seed-b" in text:
                rows.append([0.0, 1.0])
            elif "near-b" in text:
                rows.append([0.05, 0.95])
            else:
                rows.append([0.45, 0.55])
        return np.asarray(rows, dtype=np.float32)


def drift_sample() -> list[dict]:
    """Two labelled seeds and three unlabelled papers that should split."""
    return [
        {"work_id": "S-A", "pub_year": 2018, "title": "seed-a", "abstract": "", "topics": ["Alpha"]},
        {"work_id": "U1", "pub_year": 2019, "title": "mild-b one", "abstract": "", "topics": []},
        {"work_id": "U2", "pub_year": 2019, "title": "mild-b two", "abstract": "", "topics": []},
        {"work_id": "S-B", "pub_year": 2020, "title": "seed-b", "abstract": "", "topics": ["Beta"]},
        {"work_id": "U3", "pub_year": 2021, "title": "near-b three", "abstract": "", "topics": []},
    ]


def evaluate(papers: list[dict], embedder=None, batch: int = 20, k: int = 1,
            min_sim: float = 0.3, miner_cfg: dict | None = None) -> dict:
    cfg = dict(MINER)
    if miner_cfg:
        cfg.update(miner_cfg)
    labeled = [{**p, "topics": list(p.get("topics") or [])} for p in papers if p.get("topics")]
    pattern = {}
    if labeled:
        pattern = compare_patterns(
            mine_batches(labeled, batch, **cfg),
            mine_once(labeled, **cfg),
        )
    topic = {"unlabeled": 0, "topic_jaccard": 1.0, "topic_drift": 0.0,
             "papers_disagreed": 0, "topic_split_count": 0, "topic_splits": [],
             "pattern_jaccard": None, "support_mae": None}
    if embedder is not None and any(not p.get("topics") for p in papers):
        inc = assign_incremental(papers, embedder, k=k, min_sim=min_sim)
        full = assign_full(papers, embedder, k=k, min_sim=min_sim)
        topic = topic_drift_and_splits(papers, inc, full)
        inc_pat = compare_patterns(mine_batches(inc, batch, **cfg), mine_once(full, **cfg))
        topic["pattern_jaccard"] = inc_pat["pattern_jaccard"]
        topic["support_mae"] = inc_pat["support_mae"]
        topic["patterns_incremental"] = inc_pat["patterns_incremental"]
        topic["patterns_full"] = inc_pat["patterns_full"]
    return {
        "papers": len(papers),
        "fixed_topics": {"papers": len(labeled), **pattern} if pattern else {"papers": len(labeled)},
        "assigned_topics": topic,
        "topic_drift": topic["topic_drift"],
        "topic_split_count": topic["topic_split_count"],
        "topic_splits": topic["topic_splits"],
    }


def run_builtin() -> dict:
    """Fixed-topic pattern check, then the small sample that drifts and splits."""
    fixed = evaluate(fixed_topic_sample(), embedder=None, batch=20)
    drifted = evaluate(drift_sample(), embedder=_DriftEmbedder(), batch=5, k=1, min_sim=0.3,
                       miner_cfg={"min_baskets": 1, "min_support": 0.2})
    return {
        "fixed_topics": fixed["fixed_topics"],
        "assigned_topics": drifted["assigned_topics"],
        "topic_drift": drifted["topic_drift"],
        "topic_split_count": drifted["topic_split_count"],
        "topic_splits": drifted["topic_splits"],
    }


def papers_from_works(path: Path) -> list[dict]:
    from ml.papers import read_works
    rows = []
    for p in read_works(path):
        rows.append({"work_id": p.work_id, "pub_year": p.pub_year, "title": p.title,
                     "abstract": p.abstract or "", "topics": list(p.topics or [])})
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description="Incremental patterns and topics versus a full rebuild")
    ap.add_argument("--works", help="optional works JSONL. Relative paths are from the repo root")
    ap.add_argument("--batch", type=int, default=50)
    a = ap.parse_args(argv)
    if a.works:
        from ml.embeddings import get_embedder
        papers = papers_from_works(resolve(a.works))
        if not papers:
            sys.exit("no works in that file")
        report = evaluate(papers, embedder=get_embedder(), batch=a.batch)
    else:
        report = run_builtin()
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    main()
