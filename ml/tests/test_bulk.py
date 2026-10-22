import json

import pytest

from ml import bulk


def test_months_and_quotas_are_even():
    ms = bulk.months("2015-01", "2016-12")
    assert len(ms) == 24 and ms[0] == "2015-01" and ms[-1] == "2016-12"
    q = bulk.quotas(ms, 70)
    assert sum(q.values()) == 70 and max(q.values()) - min(q.values()) <= 1
    assert bulk.month_bounds("2024-02") == ("2024-02-01", "2024-02-29")


def _work(i, abstract=True):
    w = {"id": f"https://openalex.org/W{i}", "display_name": f"T{i}", "publication_year": 2020,
         "publication_date": "2020-01-01", "topics": [], "authorships": []}
    if abstract:
        w["abstract_inverted_index"] = {"hello": [0], "world": [1]}
    return w


class FakeClient:
    def __init__(self, pages):
        self.pages, self.requests, self.calls = pages, 0, []

    def get(self, params):
        self.requests += 1
        self.calls.append(params)
        return {"results": self.pages(params)}


def test_fetch_dedupes_skips_no_abstract_and_resumes(tmp_path):
    out = tmp_path / "w.jsonl"
    counter = iter(range(1, 10_000))

    def pages(p):
        works = [_work(next(counter)) for _ in range(5)]
        works.append(_work(1))               # duplicate of the first ever work
        works.append(_work(99_999, abstract=False))
        return works
    c = FakeClient(pages)
    r = bulk.fetch(6, out, start="2020-01", end="2020-03", exclude_ids={"W2"}, client=c)
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    ids = [x["id"] for x in rows]
    assert len(ids) == len(set(ids)) == r.fetched == 6
    assert "W2" not in ids and "W99999" not in ids and all("raw" not in x for x in rows)
    assert all("has_abstract:true" in call["filter"] for call in c.calls)
    # resume: every month is marked done, so nothing is requested again
    c2 = FakeClient(lambda p: pytest.fail("should not fetch"))
    r2 = bulk.fetch(6, out, start="2020-01", end="2020-03", client=c2)
    assert r2.fetched == 0 and r2.months_done == 3


def test_short_month_is_reported(tmp_path):
    c = FakeClient(lambda p: [_work(1)])
    r = bulk.fetch(5, tmp_path / "w.jsonl", start="2020-01", end="2020-01", client=c)
    assert r.short_months == {"2020-01": 4}


class Resp:
    def __init__(self, code, body=None, headers=None):
        self.status_code, self._b, self.headers, self.text = code, body or {}, headers or {}, ""

    def json(self):
        return self._b


class Session:
    def __init__(self, seq):
        self.seq, self.params = list(seq), []

    def get(self, url, params=None, timeout=None):
        self.params.append(params)
        return self.seq.pop(0)


def test_client_backs_off_and_sends_key():
    sleeps = []
    s = Session([Resp(429, headers={"Retry-After": "3"}), Resp(503), Resp(200, {"results": []})])
    c = bulk.OpenAlexClient(session=s, api_key="k", email="", min_interval=0, sleep=sleeps.append)
    assert c.get({"x": 1}) == {"results": []}
    assert sleeps == [3.0, 2.0] and s.params[0]["api_key"] == "k"


def test_client_raises_on_4xx():
    c = bulk.OpenAlexClient(session=Session([Resp(400)]), api_key="", email="", min_interval=0,
                            sleep=lambda s: None)
    with pytest.raises(RuntimeError):
        c.get({})
