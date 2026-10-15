"""Topic clusters and a stable 2D/3D layout for the paper galaxy.

Clustering prefers UMAP + HDBSCAN when both libraries are installed and there
are at least 25 papers. Otherwise it uses k-means (numpy only, no extra
dependency). Labels are c-TF-IDF keywords.

The layout is always a 3-component PCA. ``x`` and ``y`` are the 2D layout;
``x``, ``y`` and ``z`` are the 3D layout (the 2D view is the first two axes
of the same basis). The basis is saved on the first build. Later syncs
project only new or re-embedded papers into that basis and assign them to the
nearest saved centroid, so papers that were already placed keep their
coordinates and cluster id. Labels are recomputed from the current members,
so the wording can change. ``GalaxyMap.sync(..., refit=True)`` recomputes the
basis and the clusters and can move every point.

UMAP coordinates are not used for the layout: refitting UMAP would move every
paper, and the fitted reducer is not a stable on-disk format.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import re
from collections import Counter
from pathlib import Path

import numpy as np

from .text import tokens

MIN_UMAP_PAPERS = 25
MIN_SIM = 0.2
# A refit keeps a previous colour when the new centroid is at least this close
# in cosine similarity. Below that, the cluster is new and gets a fresh index.
COLOR_MATCH_MIN_SIM = 0.5
# Nearest-neighbour edges for the front end. Kept small on purpose.
LINK_NEIGHBOURS = 2
LINK_CAP = 200

def _optional_available() -> bool:
    return (importlib.util.find_spec("umap") is not None
            and importlib.util.find_spec("hdbscan") is not None)


def resolve_method(method: str, n: int) -> str:
    if method == "kmeans":
        return "kmeans"
    if method == "umap-hdbscan":
        return "umap-hdbscan"
    if n >= MIN_UMAP_PAPERS and _optional_available():
        return "umap-hdbscan"
    return "kmeans"


def k_for(n: int) -> int:
    if n < 2:
        return 1
    return int(max(2, min(8, round(math.sqrt(n / 2)))))


def _kmeans(X: np.ndarray, k: int, seed: int = 0, n_iter: int = 25) -> np.ndarray:
    n = len(X)
    k = max(1, min(int(k), n))
    rng = np.random.default_rng(seed)
    centers = [X[int(rng.integers(0, n))]]
    for _ in range(1, k):
        d2 = np.min(np.stack([((X - c) ** 2).sum(1) for c in centers], 1), 1)
        total = float(d2.sum())
        if total <= 0:
            centers.append(X[int(rng.integers(0, n))])
            continue
        centers.append(X[int(rng.choice(n, p=d2 / total))])
    C = np.stack(centers).astype(np.float64)
    labels = np.zeros(n, dtype=int)
    for _ in range(n_iter):
        d2 = np.stack([((X - C[j]) ** 2).sum(1) for j in range(k)], 1)
        labels = d2.argmin(1).astype(int)
        for j in range(k):
            mask = labels == j
            if np.any(mask):
                C[j] = X[mask].mean(0)
            else:
                nearest = d2.min(1)
                C[j] = X[int(np.argmax(nearest))]
    return labels


def _umap_hdbscan(X: np.ndarray) -> np.ndarray:
    import hdbscan
    import umap
    n = len(X)
    reducer = umap.UMAP(n_neighbors=min(15, n - 1), n_components=min(10, max(2, n - 2)),
                        metric="cosine", random_state=0, min_dist=0.0)
    Z = reducer.fit_transform(X)
    clusterer = hdbscan.HDBSCAN(min_cluster_size=max(3, n // 15), metric="euclidean")
    return np.asarray(clusterer.fit_predict(Z), dtype=int)


def cluster_ids(vectors: np.ndarray, method: str = "auto", k: int | None = None) -> tuple[np.ndarray, str]:
    """Return cluster ids (noise is -1) and the method that actually ran."""
    X = np.asarray(vectors, dtype=np.float64)
    chosen = resolve_method(method, len(X))
    if chosen == "umap-hdbscan":
        try:
            labels = _umap_hdbscan(X)
            if labels is not None and len(labels) == len(X) and not np.all(labels < 0):
                return labels.astype(int), "umap-hdbscan"
        except Exception:
            pass
    kk = k_for(len(X)) if k is None else k
    return _kmeans(X, kk), "kmeans"


def ctfidf_labels(labels, texts: list[str], n_terms: int = 3) -> dict[int, str]:
    """c-TF-IDF keywords per cluster (BERTopic-style class-based TF-IDF)."""
    groups: dict[int, list[str]] = {}
    for lab, text in zip(labels, texts):
        lab = int(lab)
        if lab < 0:
            continue
        groups.setdefault(lab, []).append(text or "")
    counts = {c: Counter(tokens(" ".join(parts))) for c, parts in groups.items()}
    counts = {c: ct for c, ct in counts.items() if ct}
    if not counts:
        return {}
    tf_all: Counter = Counter()
    lengths = {}
    for c, ct in counts.items():
        tf_all.update(ct)
        lengths[c] = sum(ct.values()) or 1
    average = sum(lengths.values()) / len(lengths)
    out = {}
    for c, ct in counts.items():
        scored = []
        for term, freq in ct.items():
            scored.append((term, (freq / lengths[c]) * math.log(1 + average / tf_all[term])))
        scored.sort(key=lambda item: (-item[1], item[0]))
        top = [term for term, _ in scored[:n_terms]]
        out[c] = ", ".join(top) if top else f"cluster {c}"
    return out


def fit_basis(vectors: np.ndarray) -> dict:
    X = np.asarray(vectors, dtype=np.float64)
    mean = X.mean(0)
    centered = X - mean
    n_comp = min(3, centered.shape[0], centered.shape[1])
    components = np.zeros((3, X.shape[1]), dtype=np.float64)
    if n_comp > 0 and np.any(centered):
        _, _, vt = np.linalg.svd(centered, full_matrices=False)
        components[:n_comp] = vt[:n_comp]
    coords = centered @ components.T
    scale = float(np.sqrt(np.mean(coords ** 2)))
    if scale < 1e-8:
        scale = 1.0
    return {"mean": mean.tolist(), "components": components.tolist(), "scale": scale}


def project(vectors: np.ndarray, basis: dict) -> np.ndarray:
    X = np.asarray(vectors, dtype=np.float64)
    mean = np.asarray(basis["mean"], dtype=np.float64)
    components = np.asarray(basis["components"], dtype=np.float64)
    scale = float(basis.get("scale") or 1.0)
    return (X - mean) @ components.T / scale


def _sig(vector: np.ndarray) -> str:
    return hashlib.sha1(np.ascontiguousarray(vector, dtype=np.float32).tobytes()).hexdigest()[:16]


def _text(meta: dict) -> str:
    return f"{meta.get('title') or ''}. {meta.get('abstract') or ''}".strip()


def _year(meta: dict) -> int | None:
    year = meta.get("pub_year")
    if year is None:
        year = meta.get("year")
    try:
        return int(year) if year is not None else None
    except (TypeError, ValueError):
        return None


def _assign(vector: np.ndarray, centroids: dict, min_sim: float) -> int:
    if not centroids:
        return -1
    names = list(centroids)
    C = np.stack([np.asarray(centroids[n], dtype=np.float64) for n in names])
    C = C / (np.linalg.norm(C, axis=1, keepdims=True) + 1e-9)
    v = np.asarray(vector, dtype=np.float64)
    v = v / (np.linalg.norm(v) + 1e-9)
    sims = C @ v
    j = int(np.argmax(sims))
    if float(sims[j]) < min_sim:
        return -1
    return int(names[j])


def _round_coord(value: float) -> float:
    return round(float(value), 6)


def _cosine(a, b) -> float:
    a = np.asarray(a, dtype=np.float64).ravel()
    b = np.asarray(b, dtype=np.float64).ravel()
    return float(np.dot(a, b) / ((np.linalg.norm(a) + 1e-9) * (np.linalg.norm(b) + 1e-9)))


def hungarian(cost: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Minimum-cost assignment for a square matrix. Returns row and column indexes."""
    cost = np.asarray(cost, dtype=np.float64)
    n = cost.shape[0]
    u = np.zeros(n + 1)
    v = np.zeros(n + 1)
    p = np.zeros(n + 1, dtype=int)
    way = np.zeros(n + 1, dtype=int)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = np.full(n + 1, np.inf)
        used = np.zeros(n + 1, dtype=bool)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = np.inf
            j1 = 0
            for j in range(1, n + 1):
                if used[j]:
                    continue
                cur = cost[i0 - 1, j - 1] - u[i0] - v[j]
                if cur < minv[j]:
                    minv[j] = cur
                    way[j] = j0
                if minv[j] < delta:
                    delta = minv[j]
                    j1 = j
            for j in range(n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    rows, cols = [], []
    for j in range(1, n + 1):
        if p[j]:
            rows.append(p[j] - 1)
            cols.append(j - 1)
    return np.asarray(rows, dtype=int), np.asarray(cols, dtype=int)


def match_cluster_colors(new_centroids: dict, prev_centroids: dict, next_color: int,
                         min_sim: float = COLOR_MATCH_MIN_SIM) -> tuple[dict[str, int], int]:
    """Match new cluster ids to previous colour indexes by centroid cosine.

    Hungarian assignment minimises cosine distance. A pair below ``min_sim``
    is left unmatched, and that new cluster receives a fresh index.
    """
    new_ids = sorted(new_centroids, key=lambda x: int(x))
    prev_ids = sorted(prev_centroids, key=lambda x: int(x))
    mapping: dict[str, int] = {}
    if not new_ids:
        return mapping, int(next_color)
    if not prev_ids:
        for cid in new_ids:
            mapping[str(cid)] = int(next_color)
            next_color += 1
        return mapping, int(next_color)
    n, m = len(new_ids), len(prev_ids)
    sim = np.zeros((n, m), dtype=np.float64)
    for i, cid in enumerate(new_ids):
        for j, pid in enumerate(prev_ids):
            sim[i, j] = _cosine(new_centroids[cid], prev_centroids[pid])
    size = max(n, m)
    # Dummy rows and columns cost more than any real pair, so they lose.
    cost = np.full((size, size), 2.0, dtype=np.float64)
    cost[:n, :m] = 1.0 - sim
    rows, cols = hungarian(cost)
    for r, c in zip(rows, cols):
        if r >= n or c >= m:
            continue
        if sim[r, c] >= min_sim:
            mapping[str(new_ids[r])] = int(prev_ids[c])
    for cid in new_ids:
        if str(cid) not in mapping:
            mapping[str(cid)] = int(next_color)
            next_color += 1
    return mapping, int(next_color)


class GalaxyMap:
    """Persisted layout. See the module docstring for the stability rule."""

    def __init__(self, path: str | Path, min_sim: float = MIN_SIM):
        self.path = Path(path)
        self.min_sim = min_sim
        self.state = self._load()

    def _load(self) -> dict:
        f = self.path / "state.json"
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
        return {}

    def _save(self) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        (self.path / "state.json").write_text(json.dumps(self.state), encoding="utf-8")

    def sync(self, ids: list[str], vectors: np.ndarray, metas: list[dict],
             refit: bool = False, method: str = "auto") -> list[dict]:
        ids = list(ids)
        metas = list(metas)
        vectors = np.asarray(vectors, dtype=np.float32)
        if len(ids) == 0:
            self.state = {}
            self._save()
            return []
        if vectors.ndim != 2 or vectors.shape[0] != len(ids) or len(metas) != len(ids):
            raise ValueError("ids, vectors and metas must be aligned")
        basis = self.state.get("basis")
        dim_mismatch = bool(basis) and len(basis.get("mean") or []) != vectors.shape[1]
        if refit or not basis or dim_mismatch:
            self._fit(ids, vectors, metas, method)
        else:
            self._incremental(ids, vectors, metas)
        return self.public(ids)

    def _fit(self, ids, vectors, metas, method: str) -> None:
        prev_centroids, next_color = self._previous_colors()
        labels, used = cluster_ids(vectors, method=method)
        basis = fit_basis(vectors)
        coords = project(vectors, basis)
        texts = [_text(m) for m in metas]
        names = ctfidf_labels(labels, texts)
        centroids = {}
        for cid in sorted({int(c) for c in labels if int(c) >= 0}):
            block = vectors[np.asarray(labels) == cid]
            centroids[str(cid)] = np.asarray(block, dtype=np.float64).mean(0).tolist()
        color_of, next_color = match_cluster_colors(centroids, prev_centroids, next_color)
        papers = {}
        for i, wid in enumerate(ids):
            papers[wid] = self._record(coords[i], int(labels[i]), metas[i], vectors[i])
        self.state = {"basis": basis, "centroids": centroids,
                      "label_names": {str(k): v for k, v in names.items()},
                      "papers": papers, "cluster_method": used, "layout": "pca",
                      "color_of": color_of, "next_color": next_color}
        self._sync_color_centroids()
        self._save()

    def _previous_colors(self) -> tuple[dict, int]:
        prev = dict(self.state.get("color_centroids") or {})
        if not prev and self.state.get("centroids"):
            color_of = self.state.get("color_of") or {}
            for cid, vec in self.state["centroids"].items():
                prev[str(color_of.get(str(cid), cid))] = vec
        return prev, int(self.state.get("next_color") or 0)

    def _sync_color_centroids(self) -> None:
        mapping = self.state.get("color_of") or {}
        saved = {}
        for cid, vec in (self.state.get("centroids") or {}).items():
            color = mapping.get(str(cid))
            if color is None:
                continue
            saved[str(color)] = vec
        self.state["color_centroids"] = saved

    def _ensure_colors(self) -> None:
        """Fill colour indexes for a layout saved before colours existed."""
        if self.state.get("color_of"):
            self._sync_color_centroids()
            return
        cents = self.state.get("centroids") or {}
        mapping = {}
        next_color = 0
        for cid in sorted(cents, key=lambda x: int(x)):
            mapping[str(cid)] = next_color
            next_color += 1
        self.state["color_of"] = mapping
        self.state["next_color"] = next_color
        self._sync_color_centroids()

    def _incremental(self, ids, vectors, metas) -> None:
        papers = self.state.setdefault("papers", {})
        keep = set(ids)
        for wid in list(papers):
            if wid not in keep:
                del papers[wid]
        pending = []
        for i, wid in enumerate(ids):
            sig = _sig(vectors[i])
            if wid not in papers or papers[wid].get("sig") != sig:
                pending.append(i)
        if pending:
            coords = project(vectors[pending], self.state["basis"])
            centroids = self.state.get("centroids") or {}
            for row, i in enumerate(pending):
                papers[ids[i]] = self._record(coords[row], _assign(vectors[i], centroids, self.min_sim),
                                               metas[i], vectors[i])
        self._refresh_centroids(ids, vectors)
        self._relabel(ids, metas)
        self._ensure_colors()
        self._save()

    def _refresh_centroids(self, ids, vectors) -> None:
        papers = self.state["papers"]
        groups: dict[str, list] = {}
        for i, wid in enumerate(ids):
            cid = int(papers[wid]["cluster_id"])
            if cid < 0:
                continue
            groups.setdefault(str(cid), []).append(np.asarray(vectors[i], dtype=np.float64))
        self.state["centroids"] = {cid: np.mean(rows, axis=0).tolist() for cid, rows in groups.items()}

    def _relabel(self, ids, metas) -> None:
        papers = self.state["papers"]
        labels = [papers[wid]["cluster_id"] for wid in ids]
        names = ctfidf_labels(labels, [_text(m) for m in metas])
        self.state["label_names"] = {str(k): v for k, v in names.items()}

    @staticmethod
    def _record(coord, cluster_id: int, meta: dict, vector: np.ndarray) -> dict:
        return {"x": _round_coord(coord[0]), "y": _round_coord(coord[1]), "z": _round_coord(coord[2]),
                "cluster_id": int(cluster_id), "year": _year(meta), "sig": _sig(vector)}

    def public(self, ids: list[str]) -> list[dict]:
        names = self.state.get("label_names") or {}
        colors = self.state.get("color_of") or {}
        out = []
        for wid in ids:
            paper = self.state["papers"][wid]
            cid = int(paper["cluster_id"])
            if cid < 0:
                label = "unclustered"
                color = -1
            else:
                label = names.get(str(cid)) or f"cluster {cid}"
                color = int(colors.get(str(cid), cid))
            out.append({"id": wid, "x": paper["x"], "y": paper["y"], "z": paper["z"],
                        "cluster_id": cid, "cluster_label": label, "year": paper.get("year"),
                        "color_index": color})
        return out


def empty_graph() -> dict:
    return {"nodes": [], "clusters": [], "links": []}


def _slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return text or "topic"


def _unique_names(points: list[dict], metas: list[dict]) -> list[str]:
    """Front-end links join on topic_name, so each node needs its own."""
    seen: dict[str, int] = {}
    names = []
    for point, meta in zip(points, metas):
        title = (meta.get("title") or "").strip() or point["id"]
        n = seen.get(title, 0)
        seen[title] = n + 1
        names.append(title if n == 0 else f"{title} ({point['id']})")
    return names


def knn_links(names: list[str], vectors: np.ndarray, neighbours: int = LINK_NEIGHBOURS,
              max_edges: int = LINK_CAP) -> list[dict]:
    """Undirected k-nearest-neighbour edges, capped at ``max_edges`` strongest."""
    names = list(names)
    X = np.asarray(vectors, dtype=np.float64)
    n = len(names)
    if n < 2 or neighbours < 1 or max_edges < 1 or X.ndim != 2 or len(X) != n:
        return []
    norms = np.linalg.norm(X, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    X = X / norms
    kk = min(int(neighbours), n - 1)
    edges: dict[tuple[str, str], float] = {}
    for i in range(n):
        sims = X @ X[i]
        sims[i] = -1.0
        chosen = np.argpartition(-sims, kk - 1)[:kk]
        for j in chosen:
            j = int(j)
            weight = float(sims[j])
            if j == i or weight <= 0 or names[i] == names[j]:
                continue
            key = tuple(sorted((names[i], names[j])))
            if key not in edges or weight > edges[key]:
                edges[key] = weight
    ranked = sorted(edges.items(), key=lambda item: (-item[1], item[0]))[:max_edges]
    return [{"source": a, "target": b, "weight": round(weight, 4)} for (a, b), weight in ranked]


def graph_from_layout(points: list[dict], vectors: np.ndarray, metas: list[dict],
                      neighbours: int = LINK_NEIGHBOURS, max_edges: int = LINK_CAP) -> dict:
    """GalaxyGraph: front-end fields plus the per-paper id, label and year."""
    if not points:
        return empty_graph()
    metas = list(metas)
    names = _unique_names(points, metas)
    cited = [int(meta.get("cited_by") or 0) for meta in metas]
    peak = max(cited) or 1
    nodes = []
    for point, meta, name, cites in zip(points, metas, names, cited):
        topics = [t for t in (meta.get("topics") or []) if t]
        topic_src = topics[0] if topics else point["id"]
        cid = str(point["cluster_id"])
        if point.get("color_index") is None:
            color = -1 if cid == "-1" else int(cid)
        else:
            color = int(point["color_index"])
        nodes.append({
            "id": point["id"],
            "topic_id": _slug(str(topic_src)),
            "topic_name": name,
            "x": point["x"], "y": point["y"], "z": point["z"],
            "cluster_id": cid,
            "cluster_label": point.get("cluster_label") or "",
            "year": point.get("year"),
            "support": round(max(cites, 1) / peak, 4),
            "color_index": color,
        })
    groups: dict[str, list[dict]] = {}
    for node in nodes:
        groups.setdefault(node["cluster_id"], []).append(node)
    clusters = []
    for cid, members in sorted(groups.items(), key=lambda item: (-len(item[1]), item[0])):
        label = members[0]["cluster_label"] or ("unclustered" if cid == "-1" else f"cluster {cid}")
        clusters.append({
            "id": cid,
            "name": label,
            "label": label,
            "centroid": {
                "x": round(sum(m["x"] for m in members) / len(members), 6),
                "y": round(sum(m["y"] for m in members) / len(members), 6),
                "z": round(sum(m["z"] for m in members) / len(members), 6),
            },
            "size": len(members),
            "color_index": int(members[0]["color_index"]),
        })
    return {"nodes": nodes, "clusters": clusters,
            "links": knn_links(names, vectors, neighbours, max_edges)}
