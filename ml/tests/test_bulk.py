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
        w["abstract_inverted_index"] = {f"word{k}": [k] for k in range(60)}
    return w


class FakeClient:
    def __init__(self, pages):
        self.pages, self.requests, self.calls = pages, 0, []

    def get(self, params):
        self.requests += 1
        self.calls.append(params)
        if params.get("per-page") == 1:
            return {"meta": {"count": 1000}, "results": []}
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
    c2.get = lambda p: pytest.fail("should not request")
    r2 = bulk.fetch(6, out, start="2020-01", end="2020-03", client=c2)
    assert r2.fetched == 0 and r2.months_done == 3


def test_short_month_is_topped_up_on_resume(tmp_path):
    out = tmp_path / "w.jsonl"
    c = FakeClient(lambda p: [_work(1)])
    r = bulk.fetch(5, out, start="2020-01", end="2020-01", client=c)
    assert r.short_months == {"2020-01": 4}
    n = iter(range(100, 200))
    c2 = FakeClient(lambda p: [_work(next(n)) for _ in range(10)])
    r2 = bulk.fetch(5, out, start="2020-01", end="2020-01", client=c2)
    assert r2.fetched == 4 and not r2.short_months
    assert c2.calls[-1]["seed"] == 43          # new sample on the top-up
    assert len(out.read_text().splitlines()) == 5


def test_quotas_subtract_existing_per_month():
    ms = ["2020-01", "2020-02", "2020-03"]
    q = bulk.quotas(ms, 30, {"2020-01": 20, "2020-02": 0, "2020-03": 4})
    assert sum(q.values()) == 30 and q["2020-01"] == 0
    totals = {m: q[m] + e for m, e in {"2020-01": 20, "2020-02": 0, "2020-03": 4}.items()}
    assert totals["2020-02"] == totals["2020-03"] == 17


def test_short_abstracts_skipped_and_rates_recorded(tmp_path):
    def pages(p):
        short = _work(1, abstract=False)
        short["abstract_inverted_index"] = {"tiny": [0]}
        return [short, _work(2)]
    rates = []
    r = bulk.fetch(1, tmp_path / "w.jsonl", start="2020-01", end="2020-01", client=FakeClient(pages),
                   existing_by_month={"2020-01": 3}, rates_sink=lambda *a: rates.append(a))
    assert r.fetched == 1
    assert rates[0][:3] == ("2020-01", 1000, 4) and "min_abstract_chars:200" in rates[0][3]


def test_local_store_sampling_rates_and_month_counts(tmp_path):
    import numpy as np
    from ml.store import LocalStore
    s = LocalStore(tmp_path)
    s.upsert(["W1", "W2"], np.ones((2, 384), dtype=np.float32), [{"created": "2020-01-05"}, {"created": None}])
    assert s.month_counts() == {"2020-01": 1}
    s.put_sampling_rate("2020-01", 1000, 5, "f")
    assert LocalStore(tmp_path).sampling_rates()["2020-01"]["sampled"] == 5


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


def test_backfill_dates_local_metadata_only_and_idempotent(tmp_path):
    import numpy as np
    from ml.store import LocalStore
    s = LocalStore(tmp_path)
    v = np.eye(3, 384, dtype=np.float32)
    s.upsert(["W1", "W2", "W3"], v, [{"created": "2023-05-01"}, {"created": "2023-05-01"},
                                     {"created": "2019-02-02", "publication_date": "2019-02-02"}], model="m")
    assert s.month_counts() == {"2023-05": 2, "2019-02": 1}

    class C:
        requests = 0
        calls = []

        def get(self, p):
            self.requests += 1
            self.calls.append(p)
            return {"results": [{"id": "https://openalex.org/W1", "publication_date": "2017-03-04"}]}
    assert bulk.backfill_dates(s, client=C(), dry_run=True).missing == 2
    c = C()
    r = bulk.backfill_dates(s, client=c, batch=1)
    assert (r.missing, r.updated, r.not_found, r.requests) == (2, 2, 1, 2)
    assert c.calls[0]["filter"] == "openalex_id:W1" and c.calls[0]["select"] == "id,publication_date"
    s2 = LocalStore(tmp_path)
    assert s2.get("W1")["publication_date"] == "2017-03-04" and s2.get("W2")["publication_date"] is None
    assert np.array_equal(s2.vecs, v) and set(s2.models.values()) == {"m"}
    assert s2.month_counts() == {"2017-03": 1, "2023-05": 1, "2019-02": 1}
    c2 = C()
    assert bulk.backfill_dates(s2, client=c2).missing == 0 and c2.requests == 0


def test_backfill_batches_of_50_with_http_backoff(tmp_path):
    import numpy as np
    from ml.store import LocalStore
    s = LocalStore(tmp_path)
    ids = [f"W{i}" for i in range(120)]
    s.upsert(ids, np.ones((120, 384), dtype=np.float32), [{} for _ in ids], model="m")
    seq = [Resp(429)] + [Resp(200, {"results": [{"id": f"https://openalex.org/{w}", "publication_date": "2020-01-01"}
                                                 for w in ids[k:k + 50]]}) for k in (0, 50, 100)]
    sess = Session(seq)
    c = bulk.OpenAlexClient(session=sess, api_key="k", email="", min_interval=0, sleep=lambda x: None)
    r = bulk.backfill_dates(s, client=c, batch=500)   # clamped to 50
    assert r.updated == 120 and r.not_found == 0 and r.requests == 4
    assert all(p["filter"].count("|") <= 49 and p["api_key"] == "k" for p in sess.params)
