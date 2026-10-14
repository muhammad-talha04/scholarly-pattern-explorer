"""Sentence embeddings with all-MiniLM-L6-v2 (384-d, free, CPU-friendly).

The model is loaded lazily so importing this module is cheap and tests can
inject a fake encoder without downloading anything.
"""
from __future__ import annotations

import hashlib
import os

import numpy as np

MODEL_NAME = os.getenv("ML_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
DIM = 384


class Embedder:
    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # heavy import
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode(self, texts: list[str]) -> np.ndarray:
        vecs = self._load().encode(list(texts), normalize_embeddings=True,
                                   convert_to_numpy=True, show_progress_bar=False)
        return np.asarray(vecs, dtype=np.float32)


class HashEmbedder:
    """Deterministic bag-of-words hashing embedder. Offline tests / emergency fallback."""

    def __init__(self, dim: int = DIM):
        self.dim = dim

    def encode(self, texts: list[str]) -> np.ndarray:
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


def get_embedder():
    """ML_EMBEDDER=hash forces the offline embedder (CI, no model download)."""
    if os.getenv("ML_EMBEDDER", "").lower() == "hash":
        return HashEmbedder()
    return Embedder()
