"""
DIAGNOSTIC: run this whenever something does not work.

    python check_setup.py

It walks through every prerequisite in order and tells you the exact next
command to run. It changes nothing and cannot break anything.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

OK, BAD, WARN = "[ OK ]", "[FAIL]", "[WARN]"
problems: list[str] = []


def say(tag: str, msg: str, fix: str = "") -> None:
    print(f"{tag} {msg}")
    if tag == BAD and fix:
        problems.append(fix)


print("=" * 68)
print("SETUP CHECK")
print("=" * 68)

# ---------------------------------------------------------------- 1. Python
v = sys.version_info
if v >= (3, 9):
    say(OK, f"Python {v.major}.{v.minor}.{v.micro}")
else:
    say(BAD, f"Python {v.major}.{v.minor} is too old", "install Python 3.9 or newer")

# ------------------------------------------------------------ 2. where am I
here = Path.cwd()
print(f"       working folder: {here}")
low = str(here).lower()
if "onedrive" in low or "dropbox" in low or "google drive" in low:
    say(WARN, "this folder is inside a cloud-synced drive (OneDrive/Dropbox)")
    print("       Database files get locked by the sync client and you will")
    print("       eventually see 'disk I/O error' in the middle of a write.")
    print("       Move the project to a plain local folder, e.g.  C:\\projects\\")

# ------------------------------------------------------- 3. virtual env live
in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
if in_venv:
    say(OK, f"virtual environment active -> {sys.prefix}")
else:
    say(BAD, "virtual environment is NOT active",
        r".venv\Scripts\activate     (macOS/Linux: source .venv/bin/activate)")

# ------------------------------------------------------------- 4. the files
need = ["dbconn.py", "schema.sql", "indexes.sql", "fpgrowth.py", "make_sample_data.py",
        "build_db.py", "mine_windows.py", "analytics.py", "app.py"]
missing = [f for f in need if not Path(f).exists()]
if missing:
    say(BAD, f"missing project files: {', '.join(missing)}",
        "you are running this from the wrong folder - cd into the project folder")
else:
    say(OK, f"all {len(need)} project files present")

if not Path(".streamlit/config.toml").exists():
    say(WARN, "no .streamlit/config.toml - the app will run, but in default colours")

# --------------------------------------------------------------- 5. packages
print("-" * 68)
for mod, why, needed_now in [
    ("pandas", "required by everything", True),
    ("numpy", "required by analytics.py", True),
    ("duckdb", "the database engine", False),
    ("streamlit", "the web app (step 4)", False),
    ("plotly", "the charts (step 4)", False),
    ("networkx", "nicer network layout (optional)", False),
    ("requests", "downloading real data (step 5)", False),
]:
    try:
        __import__(mod)
        say(OK, f"{mod:<10} installed")
    except ModuleNotFoundError:
        if needed_now:
            say(BAD, f"{mod:<10} MISSING - {why}", "pip install -r requirements.txt")
        else:
            say(WARN, f"{mod:<10} missing - {why}")

# The app uses widgets and theme keys added in Streamlit 1.46-1.49. An old
# version does not warn you: it raises TypeError halfway down the page, which
# looks like a bug in the app. Say so here instead.
try:
    import streamlit as _st
    parts = tuple(int(p) for p in _st.__version__.split(".")[:2])
    if parts < (1, 49):
        say(BAD, f"streamlit {_st.__version__} is too old for app.py",
            "pip install --upgrade streamlit")
    else:
        say(OK, f"streamlit {_st.__version__} supports every widget app.py uses")
except ModuleNotFoundError:
    pass
except Exception:                                                 # noqa: BLE001
    pass

# --------------------------------------------------------------- 6. the data
print("-" * 68)
sample = Path("data/works_sample.jsonl")
if sample.exists() and sample.stat().st_size > 0:
    say(OK, f"fake data present ({sample.stat().st_size / 1e6:.1f} MB)")
else:
    say(BAD, "no fake data yet", "python make_sample_data.py")

# ----------------------------------------------------------- 7. the database
db_found = None
for cand in ("data/openalex.duckdb", "data/openalex.sqlite"):
    p = Path(cand)
    if p.exists() and p.stat().st_size > 1024:
        db_found = cand
        break

if not db_found:
    say(BAD, "no database built yet",
        "python build_db.py --input data/works_sample.jsonl")
else:
    say(OK, f"database file: {db_found} ({Path(db_found).stat().st_size / 1e6:.1f} MB)")
    try:
        sys.path.insert(0, str(here))
        from dbconn import DB
        # Open the file we actually found, not a hardcoded name: if duckdb is
        # missing, the sqlite build is the one on disk.
        db = DB(db_found)
        n_works = int(db.df("SELECT COUNT(*) AS n FROM works").n[0])
        n_wt = int(db.df("SELECT COUNT(*) AS n FROM work_topics").n[0])
        say(OK, f"engine={db.kind}  works={n_works:,}  work_topics={n_wt:,}")

        n_pat = int(db.df("SELECT COUNT(*) AS n FROM patterns").n[0])
        if n_pat:
            wins = int(db.df(
                "SELECT COUNT(DISTINCT window_start) AS n FROM patterns").n[0])
            say(OK, f"mined patterns: {n_pat:,} rows across {wins} windows")
        else:
            say(BAD, "database has no mined patterns", "python mine_windows.py")
        db.close()
    except Exception as exc:                                      # noqa: BLE001
        say(BAD, f"could not read the database: {type(exc).__name__}: {exc}",
            "delete the file in data/ and re-run build_db.py")

# ----------------------------------------------------------------- 8. verdict
print("=" * 68)
if problems:
    print("NEXT COMMANDS, in this order:\n")
    for i, fix in enumerate(dict.fromkeys(problems), 1):
        print(f"  {i}. {fix}")
else:
    print("Everything is ready.  Try:   streamlit run app.py")
print("=" * 68)
