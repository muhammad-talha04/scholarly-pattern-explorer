import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app import ratelimit as rl


def _req(ip="1.2.3.4", fwd=None, cf=None):
    headers = []
    if cf is not None:
        headers.append((b"cf-connecting-ip", cf.encode()))
    if fwd is not None:
        headers.append((b"x-forwarded-for", fwd.encode()))
    client = None if ip is None else (ip, 1)
    return Request({"type": "http", "headers": headers, "client": client})


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
    assert e.value.status_code == 429
    # Oldest hit is at t=0, so the minute window has 58s left; Retry-After rounds up.
    assert int(e.value.headers["Retry-After"]) >= 59
    rl.check_ask(_req(), now=61)  # first hit aged out


def test_forwarded_ip_used_and_global_cap():
    rl.check_ask(_req(fwd="9.9.9.9, 10.0.0.1"), now=0)
    rl.check_ask(_req(fwd="9.9.9.9"), now=0)
    with pytest.raises(HTTPException):
        rl.check_ask(_req(fwd="9.9.9.9"), now=0)   # per-IP
    rl.check_ask(_req(fwd="8.8.8.8"), now=0)       # global now at 3
    with pytest.raises(HTTPException) as e:
        rl.check_ask(_req(fwd="7.7.7.7"), now=0)   # global
    assert e.value.status_code == 429 and int(e.value.headers["Retry-After"]) >= 1


def test_header_precedence_and_separate_buckets(monkeypatch):
    """CF-Connecting-IP wins, then the first X-Forwarded-For hop, then the socket."""
    assert rl.client_ip(_req(ip="10.0.0.9", fwd="198.51.100.2, 10.1.1.1",
                             cf="203.0.113.7")) == "203.0.113.7"
    assert rl.client_ip(_req(ip="10.0.0.9", fwd="198.51.100.2, 10.1.1.1",
                             cf="   ")) == "198.51.100.2"
    assert rl.client_ip(_req(ip="10.0.0.9", fwd="  198.51.100.2 , 10.1.1.1")) == "198.51.100.2"
    assert rl.client_ip(_req(ip="10.0.0.9", fwd=" , 198.51.100.2")) == "10.0.0.9"
    assert rl.client_ip(_req(ip="10.0.0.9")) == "10.0.0.9"
    assert rl.client_ip(_req(ip=None)) == "unknown"

    monkeypatch.setenv("ASK_RATE_PER_MIN", "1")
    monkeypatch.setenv("ASK_RATE_GLOBAL_PER_HOUR", "0")
    monkeypatch.setenv("PAPER_RATE_PER_MIN", "1")
    monkeypatch.setenv("PAPER_RATE_GLOBAL_PER_HOUR", "0")
    # Same forwarded chain, different Cloudflare IPs: two buckets.
    rl.check_ask(_req(ip="10.0.0.1", fwd="198.51.100.2", cf="203.0.113.7"), now=0)
    rl.check_ask(_req(ip="10.0.0.1", fwd="198.51.100.2", cf="203.0.113.8"), now=0)
    with pytest.raises(HTTPException) as blocked:
        rl.check_ask(_req(ip="10.0.0.1", fwd="198.51.100.2", cf="203.0.113.7"), now=1)
    assert blocked.value.status_code == 429
    assert int(blocked.value.headers["Retry-After"]) >= 1
    # No CF header: the first X-Forwarded-For hop, not the TCP peer.
    rl.check_ask(_req(ip="10.9.9.9", fwd="198.51.100.50, 10.0.0.2"), now=0)
    with pytest.raises(HTTPException):
        rl.check_ask(_req(ip="10.8.8.8", fwd="198.51.100.50, 10.0.0.3"), now=1)
    rl.check_ask(_req(ip="192.0.2.15"), now=0)
    with pytest.raises(HTTPException):
        rl.check_ask(_req(ip="192.0.2.15"), now=1)
    # Paper lookups do not consume the ask window.
    rl.check_paper(_req(ip="10.0.0.1", fwd="198.51.100.2", cf="203.0.113.7"), now=0)
    with pytest.raises(HTTPException) as paper_blocked:
        rl.check_paper(_req(ip="10.0.0.1", fwd="198.51.100.2", cf="203.0.113.7"), now=1)
    assert paper_blocked.value.status_code == 429
    assert int(paper_blocked.value.headers["Retry-After"]) >= 1


def test_paper_defaults_are_a_looser_separate_bucket(monkeypatch):
    assert rl.PAPER_RATE_PER_MIN_DEFAULT > rl.ASK_RATE_PER_MIN_DEFAULT
    assert rl.PAPER_RATE_GLOBAL_PER_HOUR_DEFAULT > rl.ASK_RATE_GLOBAL_PER_HOUR_DEFAULT
    monkeypatch.delenv("PAPER_RATE_PER_MIN", raising=False)
    monkeypatch.delenv("PAPER_RATE_GLOBAL_PER_HOUR", raising=False)
    monkeypatch.setenv("ASK_RATE_PER_MIN", "1")
    monkeypatch.setenv("ASK_RATE_GLOBAL_PER_HOUR", "0")
    req = _req(cf="203.0.113.40")
    rl.check_ask(req, now=0)
    with pytest.raises(HTTPException):
        rl.check_ask(req, now=0)
    for _ in range(rl.PAPER_RATE_PER_MIN_DEFAULT):
        rl.check_paper(req, now=0)
    with pytest.raises(HTTPException) as e:
        rl.check_paper(req, now=0)
    assert e.value.status_code == 429 and int(e.value.headers["Retry-After"]) >= 1


def test_paper_global_cap(monkeypatch):
    monkeypatch.setenv("PAPER_RATE_PER_MIN", "0")
    monkeypatch.setenv("PAPER_RATE_GLOBAL_PER_HOUR", "2")
    rl.check_paper(_req(ip="1.1.1.1"), now=0)
    rl.check_paper(_req(ip="2.2.2.2"), now=0)
    with pytest.raises(HTTPException) as e:
        rl.check_paper(_req(ip="3.3.3.3"), now=0)
    assert e.value.status_code == 429 and int(e.value.headers["Retry-After"]) >= 1


def test_zero_disables(monkeypatch):
    monkeypatch.setenv("ASK_RATE_PER_MIN", "0")
    monkeypatch.setenv("ASK_RATE_GLOBAL_PER_HOUR", "0")
    monkeypatch.setenv("PAPER_RATE_PER_MIN", "0")
    monkeypatch.setenv("PAPER_RATE_GLOBAL_PER_HOUR", "0")
    for _ in range(50):
        rl.check_ask(_req(), now=0)
        rl.check_paper(_req(), now=0)


def test_routes_return_429_with_retry_after(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    monkeypatch.setenv("ASK_RATE_PER_MIN", "1")
    monkeypatch.setenv("ASK_RATE_GLOBAL_PER_HOUR", "0")
    monkeypatch.setenv("PAPER_RATE_PER_MIN", "1")
    monkeypatch.setenv("PAPER_RATE_GLOBAL_PER_HOUR", "0")
    assert client.post("/api/v1/papers/NOPE/ask", json={"question": ""}).status_code == 422
    assert client.post("/api/v1/papers/NOPE/ask", json={"question": "x" * 501}).status_code == 422
    ask_headers = {"CF-Connecting-IP": "203.0.113.21"}
    assert client.post("/api/v1/papers/NOPE/ask", json={"question": "x"},
                       headers=ask_headers).status_code == 404
    blocked = client.post("/api/v1/papers/NOPE/ask", json={"question": "x"}, headers=ask_headers)
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) >= 1
    # A different forwarded address is still under its own ask cap.
    other = client.post(
        "/api/v1/papers/NOPE/ask", json={"question": "x"},
        headers={"X-Forwarded-For": "198.51.100.77, 10.0.0.1"})
    assert other.status_code == 404
    paper_headers = {"X-Forwarded-For": "198.51.100.88, 10.0.0.1"}
    assert client.get("/api/v1/papers/NOPE", headers=paper_headers).status_code == 404
    paper_blocked = client.get("/api/v1/papers/NOPE", headers=paper_headers)
    assert paper_blocked.status_code == 429
    assert int(paper_blocked.headers["retry-after"]) >= 1
    # The ask bucket does not block a paper lookup from the same Cloudflare IP.
    assert client.get("/api/v1/papers/NOPE", headers=ask_headers).status_code == 404
