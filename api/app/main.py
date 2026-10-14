"""Scholarly Pattern Explorer v2 API.

Phase 0 skeleton: /health is real; everything else returns typed, empty
placeholders (HTTP 200 with ``"status": "not_implemented"``) so the web app
can be wired against stable shapes before the data layer lands in Phase 1-3.
"""
from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

VERSION = "0.1.0"

app = FastAPI(title="Scholarly Pattern Explorer API", version=VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class Placeholder(BaseModel):
    status: str = "not_implemented"
    phase: str
    items: list[Any] = []


class Health(BaseModel):
    status: str
    version: str


def _todo(phase: str) -> Placeholder:
    return Placeholder(phase=phase)


@app.get("/health", response_model=Health)
def health() -> Health:
    return Health(status="ok", version=VERSION)


@app.get("/search", response_model=Placeholder)
def search(q: str = Query(..., min_length=1), limit: int = Query(20, le=100)) -> Placeholder:
    """Hybrid semantic (pgvector) + full-text search. Phase 3."""
    return _todo("P3")


@app.get("/papers/{work_id}", response_model=Placeholder)
def paper(work_id: str) -> Placeholder:
    """Paper detail with DOI / OpenAlex / OA links. Phase 2."""
    return _todo("P2")


@app.get("/papers/{work_id}/summary", response_model=Placeholder)
def paper_summary(work_id: str) -> Placeholder:
    """Cached LLM summary. Phase 3."""
    return _todo("P3")


class ChatIn(BaseModel):
    message: str


@app.post("/papers/{work_id}/chat", response_model=Placeholder)
def paper_chat(work_id: str, body: ChatIn) -> Placeholder:
    """RAG chat grounded in the paper's abstract / OA full text. Phase 3."""
    return _todo("P3")


@app.get("/patterns", response_model=Placeholder)
def patterns(window_start: int | None = None, scope: str = "", min_k: int = 2) -> Placeholder:
    """Frequent itemsets + rules for a window. Phase 2."""
    return _todo("P2")


@app.get("/patterns/lifecycles", response_model=Placeholder)
def lifecycles(keys: list[str] = Query(default=[]), scope: str = "") -> Placeholder:
    return _todo("P2")


@app.get("/countries", response_model=Placeholder)
def countries() -> Placeholder:
    """Per-country output + collaboration arcs for the globe. Phase 2."""
    return _todo("P2")


@app.get("/timeline", response_model=Placeholder)
def timeline(scope: str = "") -> Placeholder:
    """Pattern birth/death events + pipeline run history. Phase 4."""
    return _todo("P4")
