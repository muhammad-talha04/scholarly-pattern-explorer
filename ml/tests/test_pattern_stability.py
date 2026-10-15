"""Offline checks for eval/pattern_stability.py."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "eval"))
import pattern_stability as ps  # noqa: E402


def test_fixed_topics_match_a_full_rebuild():
    report = ps.evaluate(ps.fixed_topic_sample(80, seed=1), embedder=None, batch=20)
    fixed = report["fixed_topics"]
    assert fixed["patterns_full"] > 0
    assert fixed["pattern_jaccard"] == 1.0
    assert fixed["support_mae"] == 0.0
    assert fixed["patterns_only_incremental"] == 0
    assert report["topic_drift"] == 0.0
    assert report["topic_split_count"] == 0


def test_incremental_topics_drift_and_split():
    report = ps.evaluate(ps.drift_sample(), embedder=ps._DriftEmbedder(), batch=5, k=1, min_sim=0.3,
                         miner_cfg={"min_baskets": 1, "min_support": 0.2})
    topics = report["assigned_topics"]
    assert topics["unlabeled"] == 3
    assert topics["papers_disagreed"] == 2
    assert report["topic_drift"] == pytest.approx(2 / 3, abs=1e-3)
    assert report["topic_split_count"] == 1
    split = report["topic_splits"][0]
    assert split["full_topic"] == "Beta"
    assert split["incremental_topics"] == {"Alpha": 2, "Beta": 1}


def test_builtin_report_has_both_checks():
    report = ps.run_builtin()
    assert report["fixed_topics"]["pattern_jaccard"] == 1.0
    assert report["topic_drift"] > 0
    assert report["topic_split_count"] >= 1
