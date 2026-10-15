import os
import sys
from pathlib import Path

import pytest

# File backend even when the shell has DATABASE_URL, so this suite stays offline.
os.environ.pop("DATABASE_URL", None)
os.environ["ML_VECTOR_BACKEND"] = "local"

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.embeddings import HashEmbedder  # noqa: E402
from ml.papers import Paper  # noqa: E402
from ml.service import MLService, SummaryCache  # noqa: E402
from ml.store import LocalStore  # noqa: E402

PAPERS = [
    Paper("W1", "Transformers for protein structure prediction",
          "We apply transformer language models to protein folding. Attention maps reveal contacts. "
          "Our model improves accuracy on benchmark datasets. Code is released openly.",
          2021, "10.1000/abc", ["Protein Folding", "Deep Learning"]),
    Paper("W2", "Quantum error correction with surface codes",
          "Surface codes protect qubits from noise. We simulate logical error rates for large lattices. "
          "Thresholds near one percent are observed.", 2020, None, ["Quantum Computing", "Error Correction"]),
    Paper("W3", "Crop yield forecasting from satellite imagery",
          "Satellite images and weather data predict wheat yield. A gradient boosting model is trained "
          "on ten years of data. Forecast error drops by twenty percent.", 2019,
          "https://doi.org/10.2000/xyz", ["Agriculture", "Remote Sensing"]),
]


@pytest.fixture
def service(tmp_path):
    svc = MLService(embedder=HashEmbedder(), store=LocalStore(tmp_path / "vec"),
                    cache=SummaryCache(tmp_path / "s.sqlite"))
    svc.index_papers(PAPERS)
    return svc


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    monkeypatch.delenv("ML_LLM_URL", raising=False)
