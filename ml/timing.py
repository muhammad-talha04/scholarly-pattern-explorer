"""Per-request stage timings for the search path.

    with collect() as t:          # one per request (API middleware)
        with stage("embed"): ...
    t -> {"embed": 12.3, ...}     # milliseconds

Each stage is also logged at INFO on the ``spe.timing`` logger. Outside
``collect()`` stages only log, so the CLI and tests need no setup.
"""
from __future__ import annotations

import contextlib
import contextvars
import logging
import time

log = logging.getLogger("spe.timing")
_current: contextvars.ContextVar[dict | None] = contextvars.ContextVar("spe_timings", default=None)


@contextlib.contextmanager
def collect():
    timings: dict[str, float] = {}
    token = _current.set(timings)
    try:
        yield timings
    finally:
        _current.reset(token)


@contextlib.contextmanager
def stage(name: str):
    t0 = time.perf_counter()
    try:
        yield
    finally:
        ms = (time.perf_counter() - t0) * 1000
        bucket = _current.get()
        if bucket is not None:
            bucket[name] = bucket.get(name, 0.0) + ms
        log.info("stage=%s ms=%.1f", name, ms)


def server_timing(timings: dict[str, float]) -> str:
    """Server-Timing header value, e.g. ``embed;dur=12.3, vector;dur=40.1``."""
    return ", ".join(f"{k};dur={v:.1f}" for k, v in timings.items())
