import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app import ratelimit as rl


def _req(ip="1.2.3.4", fwd=None):
    headers = [(b"x-forwarded-for", fwd.encode())] if fwd else []
    return Request({"type": "http", "headers": headers, "client": (ip, 1)})


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    rl.reset()
    monkeypatch.setenv("ASK_RATE_PER_MIN", "2")
    monkeypatch.setenv("ASK_RATE_GLOBAL_PER_HOUR", "3")
    yield
    rl.reset()


def test_per_ip_limit_and_window():
    rl.check_ask(_req(), now=0)
    rl.check_ask(_req(), now=1)
    with pytest.raises(HTTPException) as e:
        rl.check_ask(_req(), now=2)
    assert e.value.status_code == 429 and int(e.value.headers["Retry-After"]) >= 1
    rl.check_ask(_req(), now=61)  # first hit aged out


def test_forwarded_ip_used_and_global_cap():
    rl.check_ask(_req(fwd="9.9.9.9, 10.0.0.1"), now=0)
    rl.check_ask(_req(fwd="9.9.9.9"), now=0)
    with pytest.raises(HTTPException):
        rl.check_ask(_req(fwd="9.9.9.9"), now=0)   # per-IP
    rl.check_ask(_req(fwd="8.8.8.8"), now=0)       # global now at 3
    with pytest.raises(HTTPException):
        rl.check_ask(_req(fwd="7.7.7.7"), now=0)   # global


def test_zero_disables(monkeypatch):
    monkeypatch.setenv("ASK_RATE_PER_MIN", "0")
    monkeypatch.setenv("ASK_RATE_GLOBAL_PER_HOUR", "0")
    for _ in range(50):
        rl.check_ask(_req(), now=0)


def test_route_returns_429_and_rejects_long_question(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    monkeypatch.setattr(rl, "check_ask", rl.check_ask)
    monkeypatch.setenv("ASK_RATE_PER_MIN", "1")
    assert client.post("/api/v1/papers/NOPE/ask", json={"question": "x" * 501}).status_code == 422
    client.post("/api/v1/papers/NOPE/ask", json={"question": "x"})
    assert client.post("/api/v1/papers/NOPE/ask", json={"question": "x"}).status_code == 429
