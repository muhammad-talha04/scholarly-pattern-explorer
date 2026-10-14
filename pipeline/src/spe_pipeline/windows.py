"""Sliding-window bookkeeping, including dirty-window detection for incremental mining.

A window [start, start+length-1] only changes when a paper inside its year range
is added, removed or re-tagged. So after an update we re-mine just the windows
that overlap the changed years and keep every other stored result.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class MiningParams:
    window: int = 3
    step: int = 1
    min_support: float = 0.02
    min_confidence: float = 0.5
    max_len: int = 3
    min_score: float = 0.0
    min_baskets: int = 20

    def hash(self) -> str:
        blob = json.dumps(asdict(self), sort_keys=True).encode()
        return hashlib.sha256(blob).hexdigest()[:16]


def all_windows(lo: int, hi: int, window: int, step: int) -> list[tuple[int, int]]:
    """Every window start..end inside [lo, hi], same rule as the v1 miner."""
    return [(y0, y0 + window - 1) for y0 in range(lo, hi - window + 2, step)]


def dirty_windows(
    changed_years: Iterable[int], lo: int, hi: int, window: int, step: int
) -> list[tuple[int, int]]:
    years = set(changed_years)
    return [(a, b) for a, b in all_windows(lo, hi, window, step)
            if any(a <= y <= b for y in years)]
