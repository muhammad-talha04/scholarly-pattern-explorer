"""The discoveries snapshot is a file today and can move onto the shared store later."""
import json

from ml.discovery_store import load_discoveries, save_discoveries


def test_save_and_load_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("ML_DATA_DIR", str(tmp_path / "ml"))
    payload = {
        "date": "2026-10-15",
        "gaps": [{"gap_score": 0.91, "example_papers": None, "items": ["Alpha", "Beta"]}],
        "emerging": [],
        "emerging_by_country": {"PK": [{"topic_name": "Growing Lasers"}]},
    }
    path = save_discoveries(payload)
    assert path == tmp_path / "ml" / "discoveries.json"
    assert load_discoveries() == payload
    dated = tmp_path / "ml" / "snapshots" / "discoveries-2026-10-15.json"
    assert json.loads(dated.read_text())["gaps"][0]["gap_score"] == 0.91
    assert json.loads(dated.read_text())["gaps"][0]["example_papers"] is None


def test_load_missing_or_corrupt_is_none(tmp_path, monkeypatch):
    monkeypatch.setenv("DISCOVERIES_PATH", str(tmp_path / "missing.json"))
    assert load_discoveries() is None
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    assert load_discoveries(bad) is None
    bad.write_text("[]", encoding="utf-8")
    assert load_discoveries(bad) is None


def test_load_reads_the_latest_file_not_the_dated_copy(tmp_path):
    path = tmp_path / "discoveries.json"
    save_discoveries({"date": "2026-10-01", "gaps": [{"gap_score": 0.1}]}, path)
    save_discoveries({"date": "2026-10-15", "gaps": [{"gap_score": 0.91}]}, path)
    assert load_discoveries(path)["date"] == "2026-10-15"
    assert load_discoveries(path)["gaps"][0]["gap_score"] == 0.91
    assert (tmp_path / "snapshots" / "discoveries-2026-10-01.json").is_file()
