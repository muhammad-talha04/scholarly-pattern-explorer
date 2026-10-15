"""Embedding-space research gaps.

Two signals, both scored from papers already in the vector index (no re-embedding):

* co-occurrence: two topics sit near each other in embedding space and both have a
  real literature, but few papers mention them together.
* density: a topic's neighbourhood is busy, and the topic itself has few papers
  relative to those neighbours.

Growing-but-small topics stay in ``ml.gaps.find_gaps``. The API merges both lists.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict

import numpy as np


def _as_vec(v) -> np.ndarray:
    return np.asarray(v, dtype=np.float32).ravel()


def _norm(v: np.ndarray) -> np.ndarray | None:
    n = float(np.linalg.norm(v))
    if n == 0.0 or not math.isfinite(n):
        return None
    return v / n


def _year(paper: dict) -> int | None:
    y = paper.get("pub_year", paper.get("year"))
    try:
        return int(y) if y is not None else None
    except (TypeError, ValueError):
        return None


def _example(paper: dict) -> dict | None:
    wid = paper.get("work_id") or paper.get("id")
    if not wid:
        return None
    return {"id": str(wid), "title": paper.get("title") or "", "year": _year(paper), "score": None}


def examples_for_topics(store, topics: list[str], n: int = 3) -> list[dict]:
    """Most recent indexed papers that carry one of ``topics``."""
    want = {t for t in topics if t}
    meta = getattr(store, "meta", None)
    if not want or not isinstance(meta, dict):
        return []
    found = []
    seen = set()
    for row in meta.values():
        if not isinstance(row, dict):
            continue
        if not want.intersection(row.get("topics") or []):
            continue
        ex = _example(row)
        if ex is None or ex["id"] in seen:
            continue
        seen.add(ex["id"])
        found.append(ex)
    found.sort(key=lambda p: (p["year"] or 0, p["id"]), reverse=True)
    return found[:n]


_works_cache: dict = {}


def examples_from_works(topics: list[str], n: int = 3, works_path=None) -> list[dict]:
    """Most recent corpus papers for ``topics``, used when they are not in the vector index yet."""
    from pathlib import Path
    from .papers import default_works_path
    want = [t for t in topics if t]
    if not want:
        return []
    path = Path(works_path) if works_path else default_works_path()
    if path is None or not path.is_file():
        return []
    key = (str(path.resolve()), path.stat().st_mtime_ns)
    if _works_cache.get("key") != key:
        index: dict[str, list[dict]] = defaultdict(list)
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                row = json.loads(line)
                names = [t for t in (row.get("topics") or []) if isinstance(t, str) and t]
                ex = _example({"work_id": row.get("id") or row.get("work_id"),
                               "title": row.get("title") or "",
                               "pub_year": row.get("year", row.get("pub_year"))})
                if ex is None:
                    continue
                for name in dict.fromkeys(names):
                    index[name].append(ex)
        for name, rows in index.items():
            rows.sort(key=lambda p: (p["year"] or 0, p["id"]), reverse=True)
            del rows[8:]
        _works_cache["key"] = key
        _works_cache["index"] = index
    index = _works_cache["index"]
    found, seen = [], set()
    pools = [list(index.get(t) or []) for t in dict.fromkeys(want)]
    while len(found) < n and any(pools):
        for pool in pools:
            while pool and len(found) < n:
                rec = pool.pop(0)
                if rec["id"] in seen:
                    continue
                seen.add(rec["id"])
                found.append(dict(rec))
                break
    return found


def _window(papers: list[dict]) -> tuple[int, int]:
    years = [y for y in (_year(p) for p in papers) if y is not None]
    if not years:
        from datetime import date
        y = date.today().year - 1
        return y, y
    return min(years), max(years)


def _pick_examples(groups: list[list[dict]], n: int = 3) -> list[dict]:
    """Round-robin across groups so each side of a gap shows up."""
    chosen, seen = [], set()
    pools = [sorted(g, key=lambda p: ((p.get("year") or 0), p.get("id") or ""), reverse=True) for g in groups]
    while len(chosen) < n and any(pools):
        for pool in pools:
            while pool:
                rec = pool.pop(0)
                if not rec.get("id") or rec["id"] in seen:
                    continue
                seen.add(rec["id"])
                chosen.append({"id": rec["id"], "title": rec.get("title") or "",
                               "year": rec.get("year"), "score": None})
                break
            if len(chosen) >= n:
                break
    return chosen


def find_semantic_gaps(papers: list[dict], vectors: np.ndarray, *,
                       min_sim: float = 0.45, min_each: int = 5, max_co_rate: float = 0.2,
                       neighbor_k: int = 3, min_neighbor: float = 5, max_density_ratio: float = 0.5,
                       limit: int = 10) -> list[dict]:
    """Rank co-occurrence gaps and low-density neighbourhoods.

    ``papers[i]`` aligns with ``vectors[i]``. Each paper needs ``topics`` and an id.
    """
    vectors = np.asarray(vectors, dtype=np.float32)
    if len(papers) == 0 or vectors.ndim != 2 or vectors.shape[0] != len(papers):
        return []

    sums: dict[str, np.ndarray] = {}
    counts: dict[str, int] = defaultdict(int)
    by_topic: dict[str, list[dict]] = defaultdict(list)
    co_papers: dict[frozenset, list[dict]] = defaultdict(list)
    co_count: dict[frozenset, int] = defaultdict(int)
    used: list[dict] = []

    for paper, raw in zip(papers, vectors):
        topics = list(dict.fromkeys(t for t in (paper.get("topics") or []) if t))
        if len(topics) == 0:
            continue
        vec = _norm(_as_vec(raw))
        if vec is None:
            continue
        ex = _example(paper)
        used.append(paper)
        for t in topics:
            if t not in sums:
                sums[t] = np.zeros_like(vec)
            sums[t] = sums[t] + vec
            counts[t] += 1
            if ex is not None:
                by_topic[t].append(ex)
        if ex is not None and len(topics) >= 2:
            for i, a in enumerate(topics):
                for b in topics[i + 1:]:
                    key = frozenset((a, b))
                    co_count[key] += 1
                    co_papers[key].append(ex)

    centroids = {}
    for t, total in sums.items():
        c = _norm(total)
        if c is not None:
            centroids[t] = c
    names = sorted(centroids)
    if len(names) < 2:
        return []

    window_start, window_end = _window(used)
    gaps: list[dict] = []

    for i, a in enumerate(names):
        for b in names[i + 1:]:
            ca, cb = counts[a], counts[b]
            if min(ca, cb) < min_each:
                continue
            sim = float(np.clip(np.dot(centroids[a], centroids[b]), -1.0, 1.0))
            if sim < min_sim:
                continue
            key = frozenset((a, b))
            co = co_count.get(key, 0)
            co_rate = co / min(ca, cb)
            if co_rate >= max_co_rate:
                continue
            rarity = 1.0 - co_rate
            balance = min(ca, cb) / max(ca, cb)
            score = sim * rarity * (0.5 + 0.5 * balance)
            if not math.isfinite(score) or score <= 0:
                continue
            busier = a if ca >= cb else b
            demand = max(ca, cb)
            left, right = sorted((a, b))
            if co == 0:
                together = f"No papers study {left} and {right} together"
            else:
                together = f"{co} {'paper' if co == 1 else 'papers'} study {left} and {right} together"
            demand_word = "paper" if demand == 1 else "papers"
            explanation = (
                f"{left} and {right} cover closely related subjects (similarity {sim:.2f}). "
                f"{together}, while {demand} {demand_word} cover {busier}."
            )
            examples = _pick_examples([co_papers.get(key, []), by_topic[a], by_topic[b]], n=3)
            gaps.append({
                "kind": "cooccurrence",
                "items": [left, right],
                "topic": f"{left} + {right}",
                "gap_score": round(score, 4),
                "paper_count": int(co),
                "growth_rate": None,
                "window_start": window_start,
                "window_end": window_end,
                "explanation": explanation,
                "example_papers": examples,
                "similarity": round(sim, 4),
            })

    for t in names:
        neigh = []
        for other in names:
            if other == t:
                continue
            sim = float(np.clip(np.dot(centroids[t], centroids[other]), -1.0, 1.0))
            if sim >= min_sim:
                neigh.append((sim, other))
        neigh.sort(key=lambda x: -x[0])
        neigh = neigh[:neighbor_k]
        if not neigh:
            continue
        nd = sum(counts[o] for _, o in neigh) / len(neigh)
        own = counts[t]
        if nd < min_neighbor or own >= nd * max_density_ratio:
            continue
        mean_sim = sum(s for s, _ in neigh) / len(neigh)
        relative = (nd - own) / nd
        score = mean_sim * relative
        if not math.isfinite(score) or score <= 0:
            continue
        near_names = [o for _, o in neigh[:3]]
        own_word = "paper" if own == 1 else "papers"
        explanation = (
            f"{t} has {own} {own_word}. The nearest topics ({', '.join(near_names)}) "
            f"average about {nd:.0f} papers, so this part of the literature is thin "
            f"next to its neighbors."
        )
        examples = _pick_examples([by_topic[t]] + [by_topic[o] for o in near_names], n=3)
        gaps.append({
            "kind": "density",
            "items": [t],
            "topic": t,
            "gap_score": round(score, 4),
            "paper_count": int(own),
            "growth_rate": None,
            "window_start": window_start,
            "window_end": window_end,
            "explanation": explanation,
            "example_papers": examples,
            "similarity": round(mean_sim, 4),
        })

    gaps.sort(key=lambda g: (-g["gap_score"], g["topic"]))
    # Same item set: keep the higher score (already sorted).
    seen, out = set(), []
    for g in gaps:
        key = tuple(g["items"])
        if key in seen:
            continue
        seen.add(key)
        out.append(g)
        if len(out) >= limit:
            break
    return out


def _papers_from_local(store) -> tuple[list[dict], np.ndarray]:
    ids = list(getattr(store, "ids", []) or [])
    vecs = getattr(store, "vecs", None)
    meta = getattr(store, "meta", {}) or {}
    if vecs is None or len(ids) == 0:
        return [], np.zeros((0, 1), dtype=np.float32)
    papers, rows = [], []
    for i, wid in enumerate(ids):
        row = dict(meta.get(wid) or {})
        row.setdefault("work_id", wid)
        papers.append(row)
        rows.append(_as_vec(vecs[i]))
    return papers, np.stack(rows)


def _papers_from_pg(store) -> tuple[list[dict], np.ndarray]:
    with store.conn.cursor() as cur:
        cur.execute("SELECT work_id, embedding::text, meta FROM paper_embeddings")
        fetched = cur.fetchall()
    papers, rows = [], []
    for wid, emb, meta in fetched:
        if isinstance(meta, str):
            meta = json.loads(meta)
        row = dict(meta or {})
        row.setdefault("work_id", wid)
        papers.append(row)
        rows.append(_as_vec(json.loads(emb)))
    if not rows:
        return [], np.zeros((0, 1), dtype=np.float32)
    return papers, np.stack(rows)


def semantic_gaps_from_store(store, **kwargs) -> list[dict]:
    """Read stored vectors. An empty index returns no gaps and does not load a model."""
    if store is None or len(store) == 0:
        return []
    if hasattr(store, "ids") and hasattr(store, "vecs"):
        papers, vecs = _papers_from_local(store)
    elif hasattr(store, "conn"):
        papers, vecs = _papers_from_pg(store)
    else:
        return []
    return find_semantic_gaps(papers, vecs, **kwargs)
