"""Data paths are anchored to the repo root, not the process working directory."""
import importlib
import json
import subprocess
import sys
from pathlib import Path

from ml import paths

ROOT = Path(__file__).resolve().parents[2]


def test_relative_paths_resolve_from_repo_root(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ML_DATA_DIR", raising=False)
    monkeypatch.delenv("COUNTRY_SNAPSHOT", raising=False)
    assert paths.REPO_ROOT == ROOT
    assert paths.ml_data_dir() == ROOT / "data" / "ml"
    assert paths.country_snapshot() == ROOT / "data" / "country_snapshot.json"
    monkeypatch.setenv("ML_DATA_DIR", "custom/ml")
    assert paths.ml_data_dir() == ROOT / "custom" / "ml"


def test_topic_country_year_db_is_root_anchored(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TOPIC_COUNTRY_YEAR_DB", raising=False)
    assert paths.topic_country_year_db() == ROOT / "data" / "topic_country_year.sqlite"
    monkeypatch.setenv("TOPIC_COUNTRY_YEAR_DB", "custom/t.sqlite")
    assert paths.topic_country_year_db() == ROOT / "custom" / "t.sqlite"
    monkeypatch.setenv("TOPIC_COUNTRY_YEAR_DB", str(tmp_path / "t.sqlite"))
    assert paths.topic_country_year_db() == tmp_path / "t.sqlite"


def test_discoveries_path_follows_ml_data_dir(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DISCOVERIES_PATH", raising=False)
    monkeypatch.delenv("ML_DATA_DIR", raising=False)
    assert paths.discoveries_path() == ROOT / "data" / "ml" / "discoveries.json"
    monkeypatch.setenv("ML_DATA_DIR", "custom/ml")
    assert paths.discoveries_path() == ROOT / "custom" / "ml" / "discoveries.json"
    monkeypatch.setenv("DISCOVERIES_PATH", "custom/discoveries.json")
    assert paths.discoveries_path() == ROOT / "custom" / "discoveries.json"
    monkeypatch.setenv("DISCOVERIES_PATH", str(tmp_path / "snap.json"))
    assert paths.discoveries_path() == tmp_path / "snap.json"


def test_absolute_env_paths_are_kept(monkeypatch, tmp_path):
    monkeypatch.setenv("ML_DATA_DIR", str(tmp_path / "ml"))
    monkeypatch.setenv("COUNTRY_SNAPSHOT", str(tmp_path / "s.json"))
    assert paths.ml_data_dir() == tmp_path / "ml"
    assert paths.country_snapshot() == tmp_path / "s.json"


def test_country_api_snapshot_is_root_anchored_from_other_cwd(tmp_path):
    """Import pipeline.country_api from an unrelated directory (as when uvicorn runs in apps/api)."""
    code = ("import sys; sys.path.insert(0, %r); import os; os.environ.pop('COUNTRY_SNAPSHOT', None); "
            "from pipeline import country_api as c; print(c.SNAPSHOT)") % str(ROOT)
    out = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, capture_output=True, text=True, check=True)
    assert Path(out.stdout.strip()) == ROOT / "data" / "country_snapshot.json"
