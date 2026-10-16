"""Seeded per-month sample ingest (no network)."""
import json
import pipeline.ingest as ing


class FakeResp:
    def __init__(self, data, code=200):
        self.status_code, self._d = code, data
    def json(self):
        return self._d


class FakeSession:
    """Serves `sample` works for a month, 200 per page, ids derived from the month."""
    def __init__(self, fail_month=None):
        self.calls, self.fail_month = [], fail_month
    def get(self, url, params, timeout):
        self.calls.append(params)
        frm = params["filter"].split(",")[0].split(":")[1]
        if frm[:7] == self.fail_month:
            return FakeResp({}, 401)
        n, page = int(params["sample"]), int(params["page"])
        assert "cursor" not in params  # sample results can't be cursor-paged
        lo, hi = (page - 1) * 200, min(page * 200, n)
        res = [{"id": f"https://openalex.org/W{frm}-{i}", "display_name": "t",
                "publication_date": frm} for i in range(lo, hi)]
        return FakeResp({"meta": {"count": n}, "results": res})


def _csv(tmp_path, rows):
    p = tmp_path / "q.csv"
    p.write_text("month,from,to,openalex_count,quota\n" + "".join(
        f"{m},{f},{t},{c},{q}\n" for m, f, t, c, q in rows))
    return p


ROWS = [("2025-01", "2025-01-01", "2025-01-31", 2000, 450),
        ("2025-02", "2025-02-01", "2025-02-28", 900, 203)]


def test_sample_mode_fetches_each_month_quota(tmp_path, monkeypatch):
    s = FakeSession()
    monkeypatch.setattr(ing, "requests", s)
    monkeypatch.setattr(ing.time, "sleep", lambda *_: None)
    monkeypatch.setattr(ing.fetch_sample, "__defaults__", (s,))
    out, man = tmp_path / "w.jsonl", tmp_path / "m.json"
    assert ing.main(["--quota-csv", str(_csv(tmp_path, ROWS)), "--out", str(out),
                     "--manifest", str(man), "--seed", "7"]) == 0
    assert len(out.read_text().splitlines()) == 653
    m = json.loads(man.read_text())
    assert m["seed"] == 7 and all(v["complete"] for v in m["months"].values())
    first = s.calls[0]
    assert first["sample"] == "450" and first["seed"] == "7" and "to_publication_date:2025-01-31" in first["filter"]
    # rerun is a no-op: finished months are skipped
    n = len(s.calls)
    assert ing.main(["--quota-csv", str(_csv(tmp_path, ROWS)), "--out", str(out),
                     "--manifest", str(man), "--seed", "7"]) == 0
    assert len(s.calls) == n


def test_sample_mode_resumes_after_failure(tmp_path, monkeypatch):
    s = FakeSession(fail_month="2025-02")
    monkeypatch.setattr(ing.time, "sleep", lambda *_: None)
    monkeypatch.setattr(ing.fetch_sample, "__defaults__", (s,))
    out, man, q = tmp_path / "w.jsonl", tmp_path / "m.json", _csv(tmp_path, ROWS)
    assert ing.main(["--quota-csv", str(q), "--out", str(out), "--manifest", str(man)]) == 1
    assert list(json.loads(man.read_text())["months"]) == ["2025-01"]
    s.fail_month = None
    assert ing.main(["--quota-csv", str(q), "--out", str(out), "--manifest", str(man)]) == 0
    assert len(out.read_text().splitlines()) == 653


def test_sample_mode_rejects_seed_change_and_oversized_quota(tmp_path, monkeypatch):
    import pytest
    s = FakeSession()
    monkeypatch.setattr(ing.time, "sleep", lambda *_: None)
    monkeypatch.setattr(ing.fetch_sample, "__defaults__", (s,))
    out, man, q = tmp_path / "w.jsonl", tmp_path / "m.json", _csv(tmp_path, ROWS)
    ing.main(["--quota-csv", str(q), "--out", str(out), "--manifest", str(man), "--seed", "1"])
    with pytest.raises(SystemExit):
        ing.main(["--quota-csv", str(q), "--out", str(out), "--manifest", str(man), "--seed", "2"])
    big = _csv(tmp_path, [("2025-01", "2025-01-01", "2025-01-31", 50000, 10001)])
    with pytest.raises(SystemExit):
        ing.read_quotas(big)


def test_committed_quota_csv_is_valid():
    from pathlib import Path
    rows = ing.read_quotas(Path(__file__).resolve().parents[2] / "deploy" / "sampling" / "monthly_quota.csv")
    assert rows and all(0 < r["quota"] <= r["openalex_count"] for r in rows)
