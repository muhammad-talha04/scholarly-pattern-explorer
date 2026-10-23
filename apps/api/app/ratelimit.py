"""In-process sliding-window limits for routes that can call an LLM.

Render's free instance runs one worker, so process memory is enough. A public
CORS-* API must not let one client drain an LLM key.

The client key is the first address that is actually present:

1. ``CF-Connecting-IP`` (Cloudflare sets this; the client cannot append to it)
2. the first ``X-Forwarded-For`` hop (Render appends its own proxy, so the
   leftmost hop is client-supplied when Cloudflare is not in front)
3. ``request.client.host``

``0`` disables a cap. Over the limit raises 429 with ``Retry-After``.

ASK_RATE_PER_MIN              POST /papers/{id}/ask, per IP, per minute. Default 5.
ASK_RATE_GLOBAL_PER_HOUR      that route, all clients, per hour. Default 200.
PAPER_RATE_PER_MIN            GET /papers/{id}, per IP, per minute. Default 60.
PAPER_RATE_GLOBAL_PER_HOUR    that route, all clients, per hour. Default 2000.
"""
import os
import threading
import time
from collections import deque

from fastapi import HTTPException, Request

ASK_RATE_PER_MIN_DEFAULT = 5
ASK_RATE_GLOBAL_PER_HOUR_DEFAULT = 200
PAPER_RATE_PER_MIN_DEFAULT = 60
PAPER_RATE_GLOBAL_PER_HOUR_DEFAULT = 2000

_lock = threading.Lock()


class _Window:
    def __init__(self) -> None:
        self.per_ip: dict[str, deque] = {}
        self.global_hits: deque = deque()


_windows = {"ask": _Window(), "paper": _Window()}


def _limit(name: str, default: int) -> int:
    try:
        return max(0, int(os.environ.get(name, default)))
    except (TypeError, ValueError):
        return default


def _first_hop(value: str | None) -> str | None:
    if not value:
        return None
    hop = value.split(",")[0].strip()
    return hop or None


def client_ip(request: Request) -> str:
    """IP the limiter buckets on. See the module docstring for precedence."""
    for header in ("cf-connecting-ip", "x-forwarded-for"):
        hop = _first_hop(request.headers.get(header))
        if hop:
            return hop
    host = request.client.host if request.client else ""
    return host or "unknown"


def _hit(q: deque, now: float, window: float, cap: int) -> float | None:
    """Drop expired hits. Return seconds until the oldest hit ages out, if at cap."""
    while q and q[0] <= now - window:
        q.popleft()
    if cap and len(q) >= cap:
        return window - (now - q[0])
    return None


def _check(request: Request, name: str, per_min_env: str, per_min_default: int,
           per_hour_env: str, per_hour_default: int, detail: str,
           now: float | None) -> None:
    now = time.monotonic() if now is None else now
    per_min = _limit(per_min_env, per_min_default)
    per_hour = _limit(per_hour_env, per_hour_default)
    window = _windows[name]
    ip = client_ip(request)
    with _lock:
        q = window.per_ip.setdefault(ip, deque())
        wait = _hit(q, now, 60, per_min) or _hit(window.global_hits, now, 3600, per_hour)
        if wait is not None:
            raise HTTPException(
                429, detail, headers={"Retry-After": str(max(1, int(wait) + 1))})
        q.append(now)
        window.global_hits.append(now)
        if len(window.per_ip) > 10000:  # drop idle clients so memory stays bounded
            stale = [k for k, v in window.per_ip.items() if not v or v[-1] <= now - 60]
            for k in stale:
                del window.per_ip[k]


def check_ask(request: Request, now: float | None = None) -> None:
    _check(request, "ask", "ASK_RATE_PER_MIN", ASK_RATE_PER_MIN_DEFAULT,
           "ASK_RATE_GLOBAL_PER_HOUR", ASK_RATE_GLOBAL_PER_HOUR_DEFAULT,
           "too many questions, try again shortly", now)


def check_paper(request: Request, now: float | None = None) -> None:
    _check(request, "paper", "PAPER_RATE_PER_MIN", PAPER_RATE_PER_MIN_DEFAULT,
           "PAPER_RATE_GLOBAL_PER_HOUR", PAPER_RATE_GLOBAL_PER_HOUR_DEFAULT,
           "too many paper lookups, try again shortly", now)


def reset() -> None:
    with _lock:
        for window in _windows.values():
            window.per_ip.clear()
            window.global_hits.clear()
