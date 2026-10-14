"""FastAPI router. Mount with `app.include_router(ml.router.router, prefix="/ml")`,
or run standalone:  uvicorn ml.router:app --reload
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel, Field

from .incremental import IncrementalMiner
from .service import MLService

router = APIRouter(tags=["ml"])


@lru_cache(maxsize=1)
def get_service() -> MLService:
    return MLService()


@lru_cache(maxsize=1)
def get_miner() -> IncrementalMiner:
    return IncrementalMiner(Path(os.getenv("ML_DATA_DIR", "data/ml")) / "patterns")


class SearchIn(BaseModel):
    query: str = Field(min_length=1)
    k: int = Field(10, ge=1, le=100)


class AskIn(BaseModel):
    question: str = Field(min_length=1)
    history: list[dict] = []


@router.get("/health")
def health():
    return {"ok": True}


@router.post("/search")
def search(body: SearchIn):
    return {"query": body.query, "results": get_service().search(body.query, body.k)}


@router.get("/search")
def search_get(q: str, k: int = 10):
    return search(SearchIn(query=q, k=k))


@router.get("/papers/{work_id}/summary")
def summary(work_id: str):
    out = get_service().summarize(work_id)
    if out is None:
        raise HTTPException(404, f"paper {work_id} not indexed")
    return out


@router.post("/papers/{work_id}/ask")
def ask(work_id: str, body: AskIn):
    out = get_service().ask(work_id, body.question, body.history)
    if out is None:
        raise HTTPException(404, f"paper {work_id} not indexed")
    return out


@router.get("/patterns")
def patterns(window_start: int | None = None, min_k: int = 1):
    rows = [r for r in get_miner().patterns()
            if r["k"] >= min_k and (window_start is None or r["window_start"] == window_start)]
    return {"patterns": rows}


@router.get("/patterns/timeline")
def timeline():
    return {"timeline": get_miner().timeline()}


app = FastAPI(title="Scholarly ML service")
app.include_router(router, prefix="/ml")
