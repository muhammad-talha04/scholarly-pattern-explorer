"""Find out EXACTLY which part of the request OpenAlex is rejecting.

Run:  python diagnose_429.py

It sends 6 tiny requests (per-page=1) and prints the status code of each.
Nothing is downloaded, nothing is written. Safe to run any time.
"""
from __future__ import annotations

import os
import time
from datetime import date, timedelta
from pathlib import Path

import requests

API = "https://api.openalex.org/works"


def load_env() -> None:
    env_path = Path(__file__).parent.absolute() / ".env"
    if not env_path.exists():
        print(f"no .env found at {env_path}")
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip().strip('"').strip("'")
    print(f"loaded {env_path}")


load_env()
KEY = os.environ.get("OPENALEX_API_KEY")
MAILTO = os.environ.get("OPENALEX_MAILTO")
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()

session = requests.Session()
session.headers.update({
    "User-Agent": f"openalex-pattern-miner/1.0 (mailto:{MAILTO or 'anonymous'})",
    "Accept": "application/json",
})

print(f"api key : {'present' if KEY else 'MISSING'}")
print(f"mailto  : {MAILTO or 'MISSING'}\n")


def probe(label: str, filter_str: str | None, *, key: bool = True, mailto: bool = True) -> int:
    params = {"per-page": "1"}
    if filter_str:
        params["filter"] = filter_str
    if mailto and MAILTO:
        params["mailto"] = MAILTO
    if key and KEY:
        params["api_key"] = KEY
    try:
        r = session.get(API, params=params, timeout=(15, 60))
    except requests.exceptions.RequestException as exc:
        print(f"{label:<46} network error: {type(exc).__name__}")
        return -1
    count = ""
    if r.status_code == 200:
        count = f"  (meta.count = {(r.json().get('meta') or {}).get('count', 0):,})"
    body = "" if r.status_code == 200 else "  " + r.text[:160].replace("\n", " ")
    print(f"{label:<46} HTTP {r.status_code}{count}{body}")
    time.sleep(1.5)
    return r.status_code


print("--- probes ---")
probe("1. no filter, key + mailto", None)
probe("2. type:article only", "type:article")
probe("3. article + CS field", "type:article,primary_topic.field.id:fields/17")
probe("4. article + CS + cited>19",
      "type:article,primary_topic.field.id:fields/17,cited_by_count:>19")
from_pub = probe("5. + from_publication_date (FREE)",
                 f"type:article,primary_topic.field.id:fields/17,"
                 f"cited_by_count:>19,from_publication_date:{YESTERDAY}")
from_upd = probe("6. + from_updated_date (PREMIUM)",
                 f"type:article,primary_topic.field.id:fields/17,"
                 f"cited_by_count:>19,from_updated_date:{YESTERDAY}")

print("\n--- verdict ---")
if from_pub == 200 and from_upd != 200:
    print("from_publication_date works, from_updated_date does not.")
    print("=> from_updated_date is a PREMIUM-only filter on your account.")
    print("=> Use the new refresh.py, which syncs by publication date instead.")
elif from_pub == 200 and from_upd == 200:
    print("Both date filters work now. Re-run refresh.py; if it still fails,")
    print("the problem is request volume, not the filters (lower --per-page).")
elif from_pub != 200:
    print("Even the free date filter is blocked, so your IP/key is throttled")
    print("right now. Wait ~30 minutes, then run this script again.")
