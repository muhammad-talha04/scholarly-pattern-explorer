"""Stub routes that fix the contract. Teams replace the bodies, not the signatures."""
from fastapi import APIRouter, HTTPException
from ..schemas import (AskRequest, AskResponse, CountryStats, PaperDetail,
                       PaperSummary, Pattern, Run, SearchResponse)

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/search", response_model=SearchResponse)
def search(q: str, limit: int = 20, country: str | None = None,
           year_from: int | None = None) -> SearchResponse:
    return SearchResponse(query=q, results=[])


@router.get("/papers/{paper_id}", response_model=PaperDetail)
def paper(paper_id: str) -> PaperDetail:
    raise HTTPException(404, "paper not found")


@router.post("/papers/{paper_id}/ask", response_model=AskResponse)
def ask(paper_id: str, body: AskRequest) -> AskResponse:
    raise HTTPException(501, "not implemented yet")


@router.get("/papers/{paper_id}/related", response_model=list[PaperSummary])
def related(paper_id: str) -> list[PaperSummary]:
    return []


@router.get("/patterns", response_model=list[Pattern])
def patterns(window: int | None = None) -> list[Pattern]:
    return []


@router.get("/countries", response_model=list[CountryStats])
def countries() -> list[CountryStats]:
    return []


@router.get("/countries/{code}", response_model=CountryStats)
def country(code: str) -> CountryStats:
    raise HTTPException(404, "country not found")


@router.get("/runs", response_model=list[Run])
def runs() -> list[Run]:
    return []
