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


def test_use_postgres_matches_get_store(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("ML_VECTOR_BACKEND", raising=False)
    assert paths.use_postgres() is False
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/db")
    assert paths.use_postgres() is True
    monkeypatch.setenv("ML_VECTOR_BACKEND", "local")
    assert paths.use_postgres() is False


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


def test_render_falls_back_to_committed_snapshots(monkeypatch, tmp_path):
    from ml import paths
    monkeypatch.delenv("ML_DATA_DIR", raising=False)
    monkeypatch.delenv("COUNTRY_SNAPSHOT", raising=False)
    monkeypatch.delenv("SPE_DEPLOY_SNAPSHOTS", raising=False)
    monkeypatch.setattr(paths, "REPO_ROOT", tmp_path)
    deployed = tmp_path / "deploy" / "data"
    (deployed / "ml").mkdir(parents=True)
    (deployed / "country_snapshot.json").write_text("{}")
    monkeypatch.setattr(paths, "DEPLOY_DATA", deployed)
    monkeypatch.delenv("RENDER", raising=False)
    assert paths.ml_data_dir() == tmp_path / "data" / "ml"
    monkeypatch.setenv("RENDER", "true")
    assert paths.ml_data_dir() == deployed / "ml"
    assert paths.country_snapshot() == deployed / "country_snapshot.json"
    monkeypatch.setenv("SPE_DEPLOY_SNAPSHOTS", "0")
    assert paths.country_snapshot() == tmp_path / "data" / "country_snapshot.json"
