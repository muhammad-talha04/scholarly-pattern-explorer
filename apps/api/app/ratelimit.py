"""In-process rate limit for /ask, so an LLM key on a public CORS-* API can't be
drained. Render free runs one worker, so process memory is enough.

ASK_RATE_PER_MIN        per client IP, default 5
ASK_RATE_GLOBAL_PER_HOUR across all clients, default 200 (0 disables either)
"""
import os
import threading
import time
from collections import deque

from fastapi import HTTPException, Request

_lock = threading.Lock()
_per_ip: dict[str, deque] = {}
_global: deque = deque()


def _limit(name: str, default: int) -> int:
    try:
        return max(0, int(os.environ.get(name, default)))
    except ValueError:
        return default


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _hit(q: deque, now: float, window: float, cap: int) -> float | None:
    """Record a hit; return seconds to wait if over cap."""
    while q and q[0] <= now - window:
        q.popleft()
    if cap and len(q) >= cap:
        return window - (now - q[0])
    return None


def check_ask(request: Request, now: float | None = None) -> None:
    now = time.monotonic() if now is None else now
    per_min, per_hour = _limit("ASK_RATE_PER_MIN", 5), _limit("ASK_RATE_GLOBAL_PER_HOUR", 200)
    ip = client_ip(request)
    with _lock:
        q = _per_ip.setdefault(ip, deque())
        wait = _hit(q, now, 60, per_min) or _hit(_global, now, 3600, per_hour)
        if wait is not None:
            raise HTTPException(429, "too many questions, try again shortly",
                                headers={"Retry-After": str(max(1, int(wait) + 1))})
        q.append(now)
        _global.append(now)
        if len(_per_ip) > 10000:  # drop idle clients so memory stays bounded
            for k in [k for k, v in _per_ip.items() if not v or v[-1] <= now - 60]:
                del _per_ip[k]


def reset() -> None:
    with _lock:
        _per_ip.clear()
        _global.clear()
