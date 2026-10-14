"""Core ML service logic, independent of the web framework."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from .embeddings import get_embedder
from .llm import chat_complete
from .papers import Paper
from .store import get_store
from .text import best_sentences, extractive_summary


class SummaryCache:
    """One summary per paper, stored forever (sqlite file; free, no server)."""

    def __init__(self, path: str | Path = ":memory:"):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.lock = threading.Lock()
        self.conn.execute("CREATE TABLE IF NOT EXISTS paper_summaries (work_id TEXT PRIMARY KEY, "
                          "summary TEXT, method TEXT, created_at TEXT)")

    def get(self, work_id):
        with self.lock:
            row = self.conn.execute("SELECT summary, method, created_at FROM paper_summaries "
                                    "WHERE work_id=?", (work_id,)).fetchone()
        return None if row is None else {"summary": row[0], "method": row[1], "created_at": row[2]}

    def put(self, work_id, summary, method):
        ts = datetime.now(timezone.utc).isoformat()
        with self.lock:
            self.conn.execute("INSERT OR IGNORE INTO paper_summaries VALUES (?,?,?,?)",
                              (work_id, summary, method, ts))
            self.conn.commit()
        return self.get(work_id)


def _link(meta: dict) -> dict:
    p = Paper(**{k: meta.get(k) for k in ("work_id", "title", "abstract", "pub_year", "doi")})
    return {"openalex_url": p.openalex_url, "doi_url": p.doi_url}


class MLService:
    def __init__(self, embedder=None, store=None, cache=None):
        self.embedder = embedder or get_embedder()
        self.store = store if store is not None else get_store()
        data_dir = Path(os.getenv("ML_DATA_DIR", "data/ml"))
        self.cache = cache or SummaryCache(data_dir / "summaries.sqlite")

    # ---- 1. embeddings ----
    def index_papers(self, papers: list[Paper], batch: int = 64) -> int:
        papers = [p for p in papers if p.text]
        for i in range(0, len(papers), batch):
            chunk = papers[i:i + batch]
            vecs = self.embedder.encode([p.text for p in chunk])
            self.store.upsert([p.work_id for p in chunk], vecs, [p.to_dict() for p in chunk])
        return len(papers)

    def get_paper(self, work_id: str) -> dict | None:
        return self.store.get(work_id)

    # ---- 2. semantic search ----
    def search(self, query: str, k: int = 10) -> list[dict]:
        q = self.embedder.encode([query])[0]
        out = []
        for wid, score, meta in self.store.search(q, k):
            out.append({"work_id": wid, "title": meta.get("title"), "pub_year": meta.get("pub_year"),
                        "score": round(score, 4), "topics": meta.get("topics", []), **_link(meta)})
        return out

    # ---- 3. summaries (cached once per paper) ----
    def summarize(self, work_id: str) -> dict | None:
        cached = self.cache.get(work_id)
        if cached:
            return {"work_id": work_id, "cached": True, **cached}
        meta = self.get_paper(work_id)
        if meta is None:
            return None
        title, abstract = meta.get("title") or "", meta.get("abstract") or ""
        summary, method = None, "extractive"
        if abstract:
            summary = chat_complete([
                {"role": "system", "content": "Summarise the paper in 2-3 plain sentences. "
                                              "Use only the given abstract."},
                {"role": "user", "content": f"Title: {title}\n\nAbstract: {abstract}"}])
            if summary:
                method = "llm"
        if not summary:
            summary = extractive_summary(title, abstract) or "No abstract available for this paper."
        row = self.cache.put(work_id, summary, method)
        return {"work_id": work_id, "cached": False, **row}

    # ---- 4. grounded chat ----
    def ask(self, work_id: str, question: str, history: list[dict] | None = None) -> dict | None:
        meta = self.get_paper(work_id)
        if meta is None:
            return None
        title, abstract = meta.get("title") or "", meta.get("abstract") or ""
        context = f"Title: {title}\n\nAbstract: {abstract}"
        evidence = best_sentences(question, f"{title}. {abstract}", n=2)
        msgs = [{"role": "system", "content":
                 "Answer questions about ONE paper using only the context below. If the context "
                 "does not contain the answer, say so.\n\n" + context}]
        msgs += [m for m in (history or []) if m.get("role") in ("user", "assistant")][-6:]
        msgs.append({"role": "user", "content": question})
        answer = chat_complete(msgs)
        if answer:
            method = "llm"
        elif evidence:
            method = "extractive"
            answer = "From the abstract: " + " ".join(s for s, _ in evidence)
        else:
            method = "extractive"
            answer = ("The abstract does not seem to address that. "
                      + ("Summary: " + extractive_summary(title, abstract, 2) if abstract else
                         "No abstract is available for this paper."))
        return {"work_id": work_id, "answer": answer, "method": method,
                "evidence": [s for s, _ in evidence], **_link(meta)}
