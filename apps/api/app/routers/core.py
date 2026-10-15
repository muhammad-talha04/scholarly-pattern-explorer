"""Stub routes that fix the contract. Teams replace the bodies, not the signatures."""
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

# pipeline/ lives at the repo root; API tests run with apps/api as the cwd.
_ROOT = Path(__file__).resolve().parents[4]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline import country_api  # noqa: E402

from ..schemas import (AskRequest, Collaboration, CountingMethod, AskResponse, CountryStats, PaperDetail,
                       PaperSummary, Pattern, Run, SearchResponse, TopicCountryYear)

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
def countries(counting: CountingMethod = "fractional") -> list[CountryStats]:
    return country_api.countries(counting)


@router.get("/countries/collaborations", response_model=list[Collaboration])
def collaborations(counting: CountingMethod = "fractional") -> list[Collaboration]:
    return country_api.collaborations(counting)


@router.get("/countries/{code}", response_model=CountryStats)
def country(code: str, counting: CountingMethod = "fractional") -> CountryStats:
    row = country_api.country(code, counting)
    if row is None:
        raise HTTPException(404, "country not found")
    return row


@router.get("/topic-country-years", response_model=list[TopicCountryYear])
def topic_country_years(topic_id: str | None = None, country: str | None = None,
                        year: int | None = None, limit: int = 1000) -> list[TopicCountryYear]:
    return country_api.topic_country_years(topic_id, country, year, limit)


@router.get("/runs", response_model=list[Run])
def runs() -> list[Run]:
    return []
