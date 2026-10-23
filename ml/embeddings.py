"""Sentence embeddings. Default model: all-MiniLM-L6-v2 (384-d, free, CPU).

The model is loaded lazily so importing this module is cheap and tests can
inject a fake encoder without downloading anything.

Set ML_EMBED_MODEL to a sentence-transformers id. Retrieval models that need a
prefix (e5, bge) get one automatically. ML_EMBEDDER=hash forces the offline
embedder used by tests (no download). ML_EMBEDDER=fastembed uses the ONNX backend
(no torch; what Render can afford), with ML_EMBED_MODEL as the model id.

The candidates compared in `python -m ml.benchmark` are all 384-d so they fit
the existing pgvector column. SPECTER2 is 768-d and needs the adapters
library, so it is not a drop-in replacement.
"""
from __future__ import annotations

import hashlib
import logging
import math
import os

import numpy as np

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_NAME = os.getenv("ML_EMBED_MODEL", DEFAULT_MODEL)
DIM = 384

# Small free models that share the default dimension.
CANDIDATE_MODELS = (
    DEFAULT_MODEL,
    "BAAI/bge-small-en-v1.5",
    "intfloat/e5-small-v2",
)

_KNOWN_DIM = {name: 384 for name in CANDIDATE_MODELS}


def text_prefixes(model_name: str) -> dict[str, str]:
    """Query and passage prefixes required by some retrieval models."""
    n = model_name.lower()
    if "/e5" in n or n.startswith("e5") or "-e5-" in n:
        return {"query": "query: ", "passage": "passage: "}
    if "bge-" in n or "/bge" in n:
        return {"query": "Represent this sentence for searching relevant passages: ", "passage": ""}
    return {"query": "", "passage": ""}


class Embedder:
    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or os.getenv("ML_EMBED_MODEL", DEFAULT_MODEL)
        self._model = None

    @property
    def dim(self) -> int:
        if self._model is not None:
            getter = getattr(self._model, "get_sentence_embedding_dimension", None)
            if getter:
                return int(getter())
        return _KNOWN_DIM.get(self.model_name, DIM)

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # heavy import
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode(self, texts: list[str], mode: str = "document") -> np.ndarray:
        if len(texts) == 0:
            return np.zeros((0, self.dim), dtype=np.float32)
        prefs = text_prefixes(self.model_name)
        prefix = prefs["query"] if mode == "query" else prefs["passage"]
        prepared = [prefix + (t or "") for t in texts] if prefix else list(texts)
        vecs = self._load().encode(prepared, normalize_embeddings=True,
                                   convert_to_numpy=True, show_progress_bar=False)
        return np.asarray(vecs, dtype=np.float32)

    def encode_documents(self, texts: list[str]) -> np.ndarray:
        return self.encode(texts, mode="document")

    def encode_queries(self, texts: list[str]) -> np.ndarray:
        return self.encode(texts, mode="query")


class HashEmbedder:
    """Deterministic bag-of-words hashing embedder. Offline tests / emergency fallback."""

    def __init__(self, dim: int = DIM):
        self.dim = dim
        self.model_name = "hash"

    def encode(self, texts: list[str], mode: str = "document") -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for r, t in enumerate(texts):
            for tok in t.lower().split():
                tok = "".join(ch for ch in tok if ch.isalnum())
                if not tok:
                    continue
                h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
                out[r, h % self.dim] += 1.0
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return out / norms

    def encode_documents(self, texts: list[str]) -> np.ndarray:
        return self.encode(texts, mode="document")

    def encode_queries(self, texts: list[str]) -> np.ndarray:
        return self.encode(texts, mode="query")


FASTEMBED_BATCH_SIZE = 32


def fastembed_cache_dir() -> str:
    """Where fastembed keeps its ONNX files.

    FASTEMBED_CACHE_PATH wins. The default is ``<repo>/.cache/fastembed``, inside the project
    dir, so a model downloaded during the Render build (``python -m ml.prefetch_model``) ships
    with the deploy. fastembed's own default is ``/tmp/fastembed_cache``, which is wiped on
    every free-tier cold start and forces a 65-90 MB download from Hugging Face.
    """
    env = os.getenv("FASTEMBED_CACHE_PATH")
    if env:
        return env
    from .paths import REPO_ROOT
    return str(REPO_ROOT / ".cache" / "fastembed")


def fastembed_version() -> str:
    try:
        from importlib.metadata import version
        return version("fastembed")
    except Exception:   # not installed (hash-only CI) or odd packaging
        return "unknown"


class FastEmbedder:
    """ONNX embedder via fastembed: no torch. Measured peak RSS inside the API with one
    query: 294 MB for bge-small-en-v1.5, 242 MB for all-MiniLM-L6-v2
    (eval/embedder-2026-10-16/REPORT.md).

    fastembed serves its own ONNX exports (Qdrant/bge-small-en-v1.5-onnx-Q is quantized), so
    these vectors are not interchangeable with sentence-transformers vectors of the same model
    id; ``model_label`` marks them with a ``fastembed:`` prefix.

    ``batch_size`` (ML_EMBED_BATCH_SIZE, default 32) is passed to ``TextEmbedding.embed``.
    fastembed's own default of 256 x 512 tokens reached 8.6 GB RSS on a 1000-paper indexer batch.
    """

    backend = "fastembed"

    def __init__(self, model_name: str | None = None, batch_size: int | None = None,
                 cache_dir: str | None = None):
        self.model_name = model_name or os.getenv("ML_EMBED_MODEL", DEFAULT_MODEL)
        self.dim = _KNOWN_DIM.get(self.model_name, DIM)
        if batch_size is None:
            batch_size = int(os.getenv("ML_EMBED_BATCH_SIZE", FASTEMBED_BATCH_SIZE))
        if batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        self.batch_size = batch_size
        self.cache_dir = cache_dir or fastembed_cache_dir()
        self._model = None

    def _load(self):
        if self._model is None:
            from fastembed import TextEmbedding  # heavy import
            self._model = TextEmbedding(self.model_name, cache_dir=self.cache_dir)
        return self._model

    def encode(self, texts: list[str], mode: str = "document") -> np.ndarray:
        if len(texts) == 0:
            return np.zeros((0, self.dim), dtype=np.float32)
        prefs = text_prefixes(self.model_name)
        prefix = prefs["query"] if mode == "query" else prefs["passage"]
        prepared = [prefix + (t or "") for t in texts]
        vecs = np.asarray(list(self._load().embed(prepared, batch_size=self.batch_size)),
                          dtype=np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vecs / norms

    def encode_documents(self, texts: list[str]) -> np.ndarray:
        return self.encode(texts, mode="document")

    def encode_queries(self, texts: list[str]) -> np.ndarray:
        return self.encode(texts, mode="query")


def get_embedder(model_name: str | None = None):
    """ML_EMBEDDER=hash forces the offline embedder (CI, no model download).

    ML_EMBEDDER=fastembed uses the ONNX backend (recommended on Render);
    anything else uses sentence-transformers.
    """
    kind = os.getenv("ML_EMBEDDER", "").lower()
    if kind == "hash":
        return HashEmbedder()
    if kind == "fastembed":
        return FastEmbedder(model_name)
    return Embedder(model_name)


HASH_MODEL_LABEL = "hash-v1"


def model_label(embedder) -> str:
    """Model name + version written to paper_embeddings.model on every upsert.

    - hash embedder -> ``hash-v1``
    - sentence-transformers -> ``<model id>@<revision>``
    - fastembed ONNX -> ``fastembed:<model id>@<revision>``

    revision is ML_EMBED_MODEL_REVISION when set; otherwise ``main`` for
    sentence-transformers and ``fastembed-<installed version>`` for fastembed (the fastembed
    release decides which ONNX export it downloads). Two labels that differ are treated as
    incompatible vector spaces by the indexer, so fastembed and torch vectors never mix.
    If you upgrade fastembed without changing the ONNX source, pin
    ML_EMBED_MODEL_REVISION to the label already in the table instead of re-embedding.
    """
    if getattr(embedder, "model_name", None) == "hash":
        return HASH_MODEL_LABEL
    name = getattr(embedder, "model_name", None) or type(embedder).__name__
    rev = os.getenv("ML_EMBED_MODEL_REVISION")
    if getattr(embedder, "backend", None) == "fastembed":
        return f"fastembed:{name}@{rev or 'fastembed-' + fastembed_version()}"
    return f"{name}@{rev or 'main'}"


# Per-model cosine floor for "no close matches". Calibrated on the live 14,159-paper corpus,
# 20 judged queries + 5 off-topic queries: eval/embedder-2026-10-16/REPORT.md.
#   MiniLM: off-topic max 0.312, weakest relevant hit 0.344  -> 0.38 keeps 99% of relevant hits
#   bge:    off-topic max 0.649, weakest relevant hit 0.673  -> 0.65 (was 0.68; lowered 2026-10-22,
#           pending chris's post-re-embed benchmark; tune with ML_MIN_SCORE, no code change)
#   hash:   off-topic queries outscore real paraphrase hits  -> no floor
BGE_MIN_SCORE_DEFAULT = 0.65
MIN_SCORE_BY_MODEL = {
    "all-minilm-l6-v2": 0.38,
    "bge-small-en-v1.5": BGE_MIN_SCORE_DEFAULT,
}


_log = logging.getLogger("spe.embeddings")

# Score-floor overrides, highest precedence first.
MIN_SCORE_ENV_KEYS = ("ML_MIN_SCORE", "SEARCH_MIN_SCORE", "ML_SEARCH_MIN_SCORE")


def _model_min_score(embedder_or_name) -> float:
    name = embedder_or_name if isinstance(embedder_or_name, str) else \
        getattr(embedder_or_name, "model_name", "") or ""
    short = name.lower().rsplit("/", 1)[-1]
    if short == "hash":
        return 0.0
    return MIN_SCORE_BY_MODEL.get(short, 0.0)


def _parse_floor(key: str, raw: str) -> float | None:
    """A cosine floor in [0, 1], or None (with a warning) when raw is unusable."""
    try:
        val = float(raw.strip())
    except (TypeError, ValueError):
        val = None
    if val is None or not math.isfinite(val) or not 0.0 <= val <= 1.0:
        _log.warning("%s=%r is not a number in [0, 1]; using the per-model default floor", key, raw)
        return None
    return val


def min_search_score(embedder_or_name) -> float:
    """Cosine floor below which a search hit is dropped ("no close matches").

    Read from the environment on every call (no restart cache). The first override that is
    set wins: ML_MIN_SCORE, then SEARCH_MIN_SCORE, then ML_SEARCH_MIN_SCORE (older); 0 turns
    the floor off. An invalid value (not a number, nan/inf, outside [0, 1]) logs a warning and
    the per-model default is used. Defaults: bge 0.65, MiniLM 0.38, hash/uncalibrated 0.0 (off).
    """
    default = _model_min_score(embedder_or_name)
    for key in MIN_SCORE_ENV_KEYS:
        raw = os.getenv(key)
        if raw is None or raw.strip() == "":
            continue
        val = _parse_floor(key, raw)
        return default if val is None else val
    return default
