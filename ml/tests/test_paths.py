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
