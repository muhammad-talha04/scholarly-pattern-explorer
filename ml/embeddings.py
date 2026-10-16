"""Sentence embeddings. Default model: all-MiniLM-L6-v2 (384-d, free, CPU).

The model is loaded lazily so importing this module is cheap and tests can
inject a fake encoder without downloading anything.

Set ML_EMBED_MODEL to a sentence-transformers id. Retrieval models that need a
prefix (e5, bge) get one automatically. ML_EMBEDDER=hash forces the offline
embedder used by tests (no download).

The candidates compared in `python -m ml.benchmark` are all 384-d so they fit
the existing pgvector column. SPECTER2 is 768-d and needs the adapters
library, so it is not a drop-in replacement.
"""
from __future__ import annotations

import hashlib
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


class FastEmbedder:
    """ONNX embedder via fastembed: no torch, ~250 MB RSS, fits Render's 512 MB."""

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or os.getenv("ML_EMBED_MODEL", DEFAULT_MODEL)
        self.dim = _KNOWN_DIM.get(self.model_name, DIM)
        self._model = None

    def _load(self):
        if self._model is None:
            from fastembed import TextEmbedding  # heavy import
            self._model = TextEmbedding(self.model_name)
        return self._model

    def encode(self, texts: list[str], mode: str = "document") -> np.ndarray:
        if len(texts) == 0:
            return np.zeros((0, self.dim), dtype=np.float32)
        prefs = text_prefixes(self.model_name)
        prefix = prefs["query"] if mode == "query" else prefs["passage"]
        prepared = [prefix + (t or "") for t in texts]
        vecs = np.asarray(list(self._load().embed(prepared)), dtype=np.float32)
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
