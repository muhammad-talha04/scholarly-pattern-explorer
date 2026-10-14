"""Incremental sliding-window pattern mining.

The batch miner (mine_windows.py) re-mines every window from the database.
Here each window keeps a compressed *basket multiset* -- {sorted topic tuple:
count} -- next to its mined patterns. When new papers arrive:

  1. papers already seen (by work_id) are skipped, so only NEW papers count;
  2. papers with no topics are assigned to existing topics by embedding
     similarity to topic centroids (optional, needs an embedder);
  3. each new paper is added to the basket multiset of every window covering
     its year -- windows untouched by new papers keep their stored patterns;
  4. touched windows are re-mined with the repo's own FP-Growth over the
     *weighted* multiset (fpgrowth._build_tree already supports weights), so
     results are exact -- identical to a full recompute -- without rescanning
     the raw corpus;
  5. a dated snapshot is written for the progress timeline.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import date, datetime, timezone
from math import ceil
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fpgrowth import _build_tree, _mine, association_rules  # noqa: E402

SEP = " | "


def weighted_frequent_itemsets(weighted, min_support=0.05, max_len=None):
    """FP-Growth over (items, weight) pairs, reusing fpgrowth.py internals."""
    n = sum(w for _, w in weighted)
    if n == 0:
        return {}, 0
    min_count = max(1, ceil(min_support * n))
    _, header = _build_tree([(list(i), w) for i, w in weighted if i], min_count)
    out: dict = {}
    if header:
        _mine(header, frozenset(), min_count, out, max_len)
    return out, n


def assign_topics(papers, topic_centroids: dict[str, np.ndarray], embedder, k=3, min_sim=0.3):
    """Give topic-less papers the k nearest existing topics (cosine on embeddings)."""
    todo = [p for p in papers if not p.get("topics")]
    if not todo or not topic_centroids:
        return papers
    names = list(topic_centroids)
    C = np.stack([topic_centroids[n] for n in names]).astype(np.float32)
    C /= np.linalg.norm(C, axis=1, keepdims=True) + 1e-9
    V = embedder.encode([f"{p.get('title', '')}. {p.get('abstract', '')}" for p in todo])
    sims = V @ C.T
    for p, row in zip(todo, sims):
        order = np.argsort(-row)[:k]
        p["topics"] = [names[i] for i in order if row[i] >= min_sim]
        p["topics_assigned"] = True
    return papers


class IncrementalMiner:
    def __init__(self, state_dir: str | Path, window=3, step=1, min_support=0.05,
                 max_len=3, min_confidence=0.5, min_baskets=20):
        self.dir = Path(state_dir)
        self.cfg = dict(window=window, step=step, min_support=min_support, max_len=max_len,
                        min_confidence=min_confidence, min_baskets=min_baskets)
        self.state = self._load()

    # ---------- persistence ----------
    def _load(self):
        f = self.dir / "state.json"
        if f.exists():
            s = json.loads(f.read_text(encoding="utf-8"))
            s["seen"] = set(s["seen"])
            return s
        return {"seen": set(), "windows": {}, "last_run": None, "runs": []}

    def save(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        s = dict(self.state, seen=sorted(self.state["seen"]))
        (self.dir / "state.json").write_text(json.dumps(s), encoding="utf-8")

    # ---------- windows ----------
    def _window_starts(self, year):
        w, step = self.cfg["window"], self.cfg["step"]
        # anchor windows at multiples of step so runs agree with each other
        first = year - w + 1
        first += (-first) % step
        return [y0 for y0 in range(first, year + 1, step)]

    def _mine_window(self, y0, win):
        weighted = [(k.split(SEP), c) for k, c in win["baskets"].items()]
        n = sum(c for _, c in weighted)
        if n < self.cfg["min_baskets"]:
            win.update(patterns=[], rules=[], n_tx=n)
            return
        itemsets, n_tx = weighted_frequent_itemsets(weighted, self.cfg["min_support"],
                                                    self.cfg["max_len"])
        win["n_tx"] = n_tx
        win["patterns"] = sorted(
            ({"itemset": SEP.join(sorted(s)), "k": len(s), "support_count": c,
              "support": c / n_tx} for s, c in itemsets.items()),
            key=lambda r: (-r["support"], r["itemset"]))
        win["rules"] = association_rules(itemsets, n_tx, self.cfg["min_confidence"])

    def update(self, papers: list[dict], run_date: str | None = None,
               embedder=None, topic_centroids=None) -> dict:
        """papers: dicts with work_id, pub_year, topics (title/abstract if assigning)."""
        started = datetime.now(timezone.utc).isoformat()
        run_date = run_date or date.today().isoformat()
        before = {k: {p["itemset"] for p in w["patterns"]} for k, w in self.state["windows"].items()}
        new = [p for p in papers if p.get("work_id") and p["work_id"] not in self.state["seen"]
               and p.get("pub_year") is not None]
        if embedder is not None and topic_centroids:
            assign_topics(new, topic_centroids, embedder)
        touched = set()
        for p in new:
            self.state["seen"].add(p["work_id"])
            items = sorted(set(p.get("topics") or []))
            if len(items) < 2:          # same rule as mine_windows.baskets_for_window
                continue
            key = SEP.join(items)
            for y0 in self._window_starts(int(p["pub_year"])):
                win = self.state["windows"].setdefault(str(y0), {
                    "window_start": y0, "window_end": y0 + self.cfg["window"] - 1,
                    "baskets": {}, "patterns": [], "rules": [], "n_tx": 0})
                win["baskets"][key] = win["baskets"].get(key, 0) + 1
                touched.add(str(y0))
        changed = 0
        for y0 in touched:
            self._mine_window(y0, self.state["windows"][y0])
            changed += len(before.get(y0, set()) ^ {p["itemset"] for p in self.state["windows"][y0]["patterns"]})
        summary = {"id": len(self.state["runs"]) + 1, "run_date": run_date,
                   "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
                   "status": "success", "new_papers": len(new), "patterns_changed": changed,
                   "windows_updated": sorted(int(t) for t in touched),
                   "total_papers": len(self.state["seen"])}
        self.state["last_run"] = run_date
        self.state["runs"].append(summary)
        self.save()
        self.write_snapshot(run_date)
        return summary

    # ---------- outputs ----------
    def patterns(self):
        rows = []
        for win in sorted(self.state["windows"].values(), key=lambda w: w["window_start"]):
            for p in win["patterns"]:
                rows.append({"window_start": win["window_start"], "window_end": win["window_end"],
                             "n_tx": win["n_tx"], **p})
        return rows

    def runs(self) -> list[dict]:
        return list(self.state["runs"])

    def write_snapshot(self, run_date):
        snap_dir = self.dir / "snapshots"
        snap_dir.mkdir(parents=True, exist_ok=True)
        top = {}
        for r in self.patterns():
            if r["k"] >= 2:
                top.setdefault(r["window_start"], []).append(
                    {"itemset": r["itemset"], "support": round(r["support"], 5)})
        snap = {"date": run_date, "total_papers": len(self.state["seen"]),
                "n_windows": len(self.state["windows"]),
                "n_patterns": sum(len(w["patterns"]) for w in self.state["windows"].values()),
                "top_pairs_by_window": {str(k): v[:20] for k, v in sorted(top.items())}}
        (snap_dir / f"{run_date}.json").write_text(json.dumps(snap, indent=1), encoding="utf-8")
        return snap

    def timeline(self):
        snap_dir = self.dir / "snapshots"
        out = []
        for f in sorted(snap_dir.glob("*.json")) if snap_dir.exists() else []:
            s = json.loads(f.read_text(encoding="utf-8"))
            out.append({k: s[k] for k in ("date", "total_papers", "n_windows", "n_patterns")})
        return out


def papers_since_from_db(db, since_year: int | None = None):
    """Read papers + topics from the repo's DuckDB/SQLite (dbconn.DB) as dicts."""
    sql = ("SELECT w.work_id, w.pub_year, t.display_name FROM works w "
           "JOIN work_topics wt ON wt.work_id = w.work_id "
           "JOIN topics t ON t.topic_id = wt.topic_id")
    params = []
    if since_year is not None:
        sql += " WHERE w.pub_year >= ?"
        params.append(since_year)
    df = db.df(sql, params)
    grouped = {}
    for wid, yr, topic in df.itertuples(index=False):
        grouped.setdefault(wid, {"work_id": wid, "pub_year": int(yr), "topics": []})["topics"].append(topic)
    return list(grouped.values())
