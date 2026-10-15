"""Shared offline fixtures for cross-PR integration tests (no network, no model download)."""
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "apps" / "api"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

os.environ.setdefault("ML_EMBEDDER", "hash")
os.environ.setdefault("ML_DATA_DIR", tempfile.mkdtemp(prefix="ml-it-"))
os.environ["ML_VECTOR_BACKEND"] = "local"
os.environ.pop("DATABASE_URL", None)
os.environ.pop("ML_LLM_URL", None)


def openalex_work(n, year, topics, countries_per_author, title=None, abstract=None,
                  oa_url=None, doi=None):
    """A raw OpenAlex /works result as pipeline/ingest.py receives it."""
    words = (abstract or f"Study number {n} about {' and '.join(topics) or 'nothing'}. "
             f"Results improve on prior work.").split()
    inv = {}
    for i, w in enumerate(words):
        inv.setdefault(w, []).append(i)
    return {
        "id": f"https://openalex.org/W{n}",
        "doi": doi,
        "display_name": title or f"Paper {n} on {', '.join(topics)}",
        "publication_year": year,
        "publication_date": f"{year}-06-01",
        "cited_by_count": n,
        "topics": [{"display_name": t} for t in topics],
        "authorships": [{"author": {"display_name": f"Author {n}.{i}"}, "countries": cs,
                         "institutions": []} for i, cs in enumerate(countries_per_author)],
        "abstract_inverted_index": inv,
        "open_access": {"oa_url": oa_url},
        "primary_location": {"landing_page_url": f"https://example.org/w{n}"},
    }


def _batch1():
    return [
        openalex_work(1, 2021, ["Protein Folding", "Deep Learning"], [["PK"], ["CA", "PK"]],
                      title="Transformers for protein structure prediction",
                      abstract="We apply transformer language models to protein folding.",
                      oa_url="https://example.org/w1.pdf", doi="https://doi.org/10.1/a"),
        openalex_work(2, 2022, ["Protein Folding", "Deep Learning"], [["CA"]]),
        openalex_work(3, 2022, ["Quantum Computing", "Error Correction"], [["US"], ["DE"]],
                      title="Quantum error correction with surface codes"),
        openalex_work(4, 2023, ["Quantum Computing", "Deep Learning"], [["US"], ["US", "PK"]]),
        openalex_work(5, 2023, ["Remote Sensing", "Agriculture"], [["PK"]]),
    ]


def _batch2():
    # overlaps W5 (re-fetched because of --overlap-days) plus new works
    return [
        openalex_work(5, 2023, ["Remote Sensing", "Agriculture"], [["PK"]]),
        openalex_work(6, 2024, ["Protein Folding", "Deep Learning"], [["CA"], ["GB"]]),
        openalex_work(7, 2024, ["Remote Sensing", "Deep Learning"], [["PK"], ["CN"]]),
        openalex_work(8, 2025, ["Quantum Computing", "Error Correction"], [["DE"]]),
    ]


@pytest.fixture
def raw_batches():
    return _batch1(), _batch2()
