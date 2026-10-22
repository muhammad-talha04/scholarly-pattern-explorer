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
# Nearest-neighbour edges for the front end. Kept small on purpose.
LINK_NEIGHBOURS = 2
LINK_CAP = 200
# Generic words that win c-TF-IDF on broad clusters. Kept out of text.STOP so
# summaries and grounded answers still see them.
LABEL_STOP = frozenset("""
ai artificial intelligence learn learning learned machine
model models modeling modelling
data dataset datasets
study studies multi multiple
based approach approaches method methods
result results analysis research paper papers
system systems network networks
deep neural algorithm algorithms
proposed novel new towards large small
""".split())

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
    """c-TF-IDF keywords per cluster (BERTopic-style class-based TF-IDF).

    Generic boilerplate (``ai``, ``learning``, ``model``, ``data``, and the
    rest of ``LABEL_STOP``) is dropped. A cluster whose every term is generic
    keeps the unfiltered keywords so the label is not empty.
    """
    groups: dict[int, list[str]] = {}
    for lab, text in zip(labels, texts):
        lab = int(lab)
        if lab < 0:
            continue
        groups.setdefault(lab, []).append(text or "")
    raw = {c: Counter(tokens(" ".join(parts))) for c, parts in groups.items()}
    raw = {c: ct for c, ct in raw.items() if ct}
    if not raw:
        return {}
    counts = {}
    for c, ct in raw.items():
        kept = Counter({term: freq for term, freq in ct.items() if term not in LABEL_STOP})
        counts[c] = kept or ct
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
        labels, used = cluster_ids(vectors, method=method)
        basis = fit_basis(vectors)
        coords = project(vectors, basis)
        texts = [_text(m) for m in metas]
        names = ctfidf_labels(labels, texts)
        centroids = {}
        for cid in sorted({int(c) for c in labels if int(c) >= 0}):
            block = vectors[np.asarray(labels) == cid]
            centroids[str(cid)] = np.asarray(block, dtype=np.float64).mean(0).tolist()
        papers = {}
        for i, wid in enumerate(ids):
            papers[wid] = self._record(coords[i], int(labels[i]), metas[i], vectors[i])
        self.state = {"basis": basis, "centroids": centroids,
                      "label_names": {str(k): v for k, v in names.items()},
                      "papers": papers, "cluster_method": used, "layout": "pca"}
        self._save()

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
        out = []
        for wid in ids:
            paper = self.state["papers"][wid]
            cid = int(paper["cluster_id"])
            if cid < 0:
                label = "unclustered"
            else:
                label = names.get(str(cid)) or f"cluster {cid}"
            out.append({"id": wid, "x": paper["x"], "y": paper["y"], "z": paper["z"],
                        "cluster_id": cid, "cluster_label": label, "year": paper.get("year")})
        return out


def empty_graph() -> dict:
    return {"nodes": [], "clusters": [], "links": []}


def _slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return text or "topic"


def _paper_title(meta: dict, point_id: str) -> str:
    title = str(meta.get("title") or "").strip()
    return title or str(point_id)


def _openalex_topic(meta: dict) -> str:
    """OpenAlex display name stored on the embedding meta as ``topics[0]``."""
    for topic in meta.get("topics") or []:
        text = str(topic).strip()
        if text:
            return text
    return ""


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
    """GalaxyGraph: one node per paper, links keyed on the work id.

    ``title`` is the paper title. ``topic_name`` is the OpenAlex display name
    (``meta.topics[0]``), or the title when the paper has no topic.
    """
    if not points:
        return empty_graph()
    metas = list(metas)
    cited = [int(meta.get("cited_by") or 0) for meta in metas]
    peak = max(cited) or 1
    nodes = []
    ids = []
    for point, meta, cites in zip(points, metas, cited):
        title = _paper_title(meta, point["id"])
        topic = _openalex_topic(meta) or title
        cid = str(point["cluster_id"])
        ids.append(point["id"])
        nodes.append({
            "id": point["id"],
            "title": title,
            "topic_id": _slug(topic),
            "topic_name": topic,
            "x": point["x"], "y": point["y"], "z": point["z"],
            "cluster_id": cid,
            "cluster_label": point.get("cluster_label") or "",
            "year": point.get("year"),
            "support": round(max(cites, 1) / peak, 4),
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
        })
    return {"nodes": nodes, "clusters": clusters,
            "links": knn_links(ids, vectors, neighbours, max_edges)}


# ---- representative samples for GET /galaxy?limit=N ----
SAMPLE_SEED = 20261016
SAMPLE_MIN_PER_CLUSTER = 3
HERO_SAMPLE_SIZE = 600   # stored as document kind "galaxy_sample" at build time


def _tiebreak(node_id: str, seed: int) -> int:
    import hashlib
    return int.from_bytes(hashlib.blake2b(f"{seed}:{node_id}".encode(), digest_size=8).digest(), "big")


def _quotas(sizes: dict[str, int], limit: int, min_per: int) -> dict[str, int]:
    """Proportional to cluster size (largest remainder), at least ``min_per`` each.

    When ``limit`` cannot give every cluster its minimum, the biggest clusters get it first.
    """
    total = sum(sizes.values())
    if limit >= total:
        return dict(sizes)
    order = sorted(sizes, key=lambda c: (-sizes[c], c))
    q = {c: 0 for c in sizes}
    budget = limit
    for c in order:                                   # floors first
        take = min(min_per, sizes[c], budget)
        q[c] = take
        budget -= take
        if budget == 0:
            return q
    rest = {c: sizes[c] - q[c] for c in sizes}
    pool = sum(rest.values())
    shares = {c: budget * rest[c] / pool for c in sizes}
    for c in sizes:
        q[c] += int(shares[c])
    left = limit - sum(q.values())
    for c in sorted(sizes, key=lambda c: (-(shares[c] - int(shares[c])), -sizes[c], c)):
        if left <= 0:
            break
        if q[c] < sizes[c]:
            q[c] += 1
            left -= 1
    return q


def sample_graph(graph: dict, limit: int, min_per_cluster: int = SAMPLE_MIN_PER_CLUSTER,
                 seed: int = SAMPLE_SEED) -> dict:
    """Deterministic stratified sample with the same shape as the full graph.

    Per cluster, nodes are kept in order of support (citations), then year (newest),
    then a seeded hash of the id. Clusters are unchanged (they describe the whole
    corpus). Links are kept only when both ends survive.
    """
    nodes = list(graph.get("nodes") or [])
    limit = max(0, int(limit))
    if limit >= len(nodes):
        return graph
    groups: dict[str, list[dict]] = {}
    for n in nodes:
        groups.setdefault(str(n.get("cluster_id")), []).append(n)
    quotas = _quotas({c: len(m) for c, m in groups.items()}, limit, min_per_cluster)
    keep: set[int] = set()
    for c, members in groups.items():
        ranked = sorted(members, key=lambda n: (-(n.get("support") or 0), -(n.get("year") or 0),
                                                _tiebreak(str(n.get("id")), seed)))
        keep.update(id(n) for n in ranked[:quotas[c]])
    picked = [n for n in nodes if id(n) in keep]      # original order: stable output
    names = {n.get("topic_name") for n in picked} | {n.get("id") for n in picked}
    links = [e for e in (graph.get("links") or [])
             if e.get("source") in names and e.get("target") in names]
    return {**graph, "nodes": picked, "links": links}
