"""Download a fastembed ONNX model into the project cache at build time.

    python -m ml.prefetch_model                       # ML_PREFETCH_MODEL, default bge-small-en-v1.5
    python -m ml.prefetch_model sentence-transformers/all-MiniLM-L6-v2

Render's free tier wipes /tmp on every cold start, so the model is stored under
``fastembed_cache_dir()`` (``<repo>/.cache/fastembed`` or FASTEMBED_CACHE_PATH), which is part
of the build output. The API then loads it from disk instead of downloading 65-90 MB from
Hugging Face at the first search.

While ML_EMBEDDER is not ``fastembed`` (production today is ``hash``), a failed download only
prints a warning and exits 0, so a Hugging Face hiccup cannot break a hash deploy. With
ML_EMBEDDER=fastembed a failure exits 1 and stops the build.
"""
from __future__ import annotations

import os
import sys
import time

from .embeddings import FastEmbedder, fastembed_cache_dir

DEFAULT_PREFETCH_MODEL = "BAAI/bge-small-en-v1.5"


def prefetch(model_name: str) -> float:
    t0 = time.time()
    emb = FastEmbedder(model_name, cache_dir=fastembed_cache_dir())
    vec = emb.encode_queries(["warm-up"])          # downloads and proves the model loads
    assert vec.shape[1] == emb.dim, f"{model_name}: got dim {vec.shape[1]}, expected {emb.dim}"
    return time.time() - t0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    names = argv or [os.getenv("ML_PREFETCH_MODEL")
                     or (os.getenv("ML_EMBED_MODEL") if os.getenv("ML_EMBEDDER", "").lower() == "fastembed" else None)
                     or DEFAULT_PREFETCH_MODEL]
    required = os.getenv("ML_EMBEDDER", "").lower() == "fastembed"
    for name in names:
        try:
            dt = prefetch(name)
            print(f"prefetch: {name} ready in {fastembed_cache_dir()} ({dt:.1f}s)")
        except Exception as exc:   # noqa: BLE001 - report and decide below
            print(f"prefetch: {name} failed: {exc}", file=sys.stderr)
            if required:
                return 1
            print("prefetch: ML_EMBEDDER is not fastembed, continuing", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
