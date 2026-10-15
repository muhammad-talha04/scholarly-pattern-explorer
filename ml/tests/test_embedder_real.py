"""End-to-end check of the real MiniLM model. Skipped unless explicitly requested.

    ML_RUN_REAL_EMBED=1 python -m pytest ml/tests/test_embedder_real.py -q
"""
import os

import numpy as np
import pytest

from ml.benchmark import load_papers
from ml.embeddings import DEFAULT_MODEL, Embedder
from ml.paths import REPO_ROOT
from ml.service import MLService, SummaryCache
from ml.store import LocalStore

pytestmark = pytest.mark.skipif(os.getenv("ML_RUN_REAL_EMBED") != "1",
                                reason="set ML_RUN_REAL_EMBED=1 to download the embedding model")


def test_minilm_indexes_and_searches(tmp_path):
    papers = load_papers(REPO_ROOT / "eval" / "benchmark_sample_papers.json")
    embedder = Embedder(DEFAULT_MODEL)
    vec = embedder.encode_documents(["quantum error correction with surface codes"])
    assert vec.shape == (1, 384)
    assert abs(float(np.linalg.norm(vec)) - 1) < 1e-3
    svc = MLService(embedder=embedder, store=LocalStore(tmp_path / "v"),
                    cache=SummaryCache(":memory:"), galaxy_dir=tmp_path / "g")
    assert svc.index_papers(papers) == len(papers)
    hits = svc.search("quantum error correction with surface codes", k=5)
    assert hits[0]["work_id"] in {"W01", "W02"}
    points = {p["id"]: p for p in svc.rebuild_galaxy()["nodes"]}
    assert set(points) == {p.work_id for p in papers}

    def dist(a, b):
        pa, pb = points[a], points[b]
        return (pa["x"] - pb["x"]) ** 2 + (pa["y"] - pb["y"]) ** 2 + (pa["z"] - pb["z"]) ** 2

    assert dist("W01", "W02") < dist("W01", "W16")
