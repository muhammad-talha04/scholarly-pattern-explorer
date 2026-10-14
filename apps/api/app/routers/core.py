"""Contract routes. Bodies are wired to the ML package (ml/) via app.ml_bridge."""
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from .. import ml_bridge as ml
from ..schemas import (AskRequest, AskResponse, Collaboration, CountingMethod, CountryStats, PaperDetail,
                       PaperSummary, Pattern, Run, SearchResponse)

router = APIRouter()


def _summary_model(hit: dict) -> PaperSummary:
    return PaperSummary(id=hit["work_id"], title=hit.get("title") or "",
                        authors=hit.get("authors") or [], year=hit.get("pub_year"),
                        cited_by=hit.get("cited_by") or 0, score=hit.get("score"),
                        one_line_summary=ml.one_line(ml.get_service().cached_summary(hit["work_id"])))


def _url(u):
    """HttpUrl fields: drop values pydantic would reject instead of failing the request."""
    if not u:
        return None
    try:
        PaperDetail.model_validate({"id": "x", "title": "x", "original_url": u})
        return u
    except ValidationError:
        return None


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/search", response_model=SearchResponse)
def search(q: str, limit: int = 20, country: str | None = None,
           year_from: int | None = None) -> SearchResponse:
    hits = ml.get_service().search(q, k=max(1, min(limit, 100)), country=country,
                                   year_from=year_from)
    return SearchResponse(query=q, results=[_summary_model(h) for h in hits])


@router.get("/papers/{paper_id}", response_model=PaperDetail)
def paper(paper_id: str) -> PaperDetail:
    svc = ml.get_service()
    meta = svc.get_paper(paper_id)
    if meta is None:
        raise HTTPException(404, "paper not found")
    summ = (svc.summarize(paper_id) or {}).get("summary")
    links = svc.links(meta)
    return PaperDetail(
        id=paper_id, title=meta.get("title") or "", authors=meta.get("authors") or [],
        year=meta.get("pub_year"), cited_by=meta.get("cited_by") or 0,
        one_line_summary=ml.one_line(summ), abstract=meta.get("abstract") or None,
        summary=summ, topics=meta.get("topics") or [], countries=meta.get("countries") or [],
        original_url=_url(links["original_url"]), openalex_url=_url(links["openalex_url"]))


@router.post("/papers/{paper_id}/ask", response_model=AskResponse)
def ask(paper_id: str, body: AskRequest) -> AskResponse:
    out = ml.get_service().ask(paper_id, body.question)
    if out is None:
        raise HTTPException(404, "paper not found")
    return AskResponse(answer=out["answer"], sources=out["evidence"])


@router.get("/papers/{paper_id}/related", response_model=list[PaperSummary])
def related(paper_id: str, limit: int = 10) -> list[PaperSummary]:
    hits = ml.get_service().related(paper_id, k=max(1, min(limit, 50)))
    if hits is None:
        raise HTTPException(404, "paper not found")
    return [_summary_model(h) for h in hits]


@router.get("/patterns", response_model=list[Pattern])
def patterns(window: int | None = None, trend: str | None = None) -> list[Pattern]:
    if trend == "gap":
        # Hook for the research-gap finder (owner: michal). Not implemented here.
        raise HTTPException(501, "trend=gap is not implemented yet")
    rows = ml.get_miner().patterns()
    return [Pattern(items=r["itemset"].split(" | "), support=r["support"],
                    window_start=r["window_start"], window_end=r["window_end"])
            for r in rows if window is None or r["window_start"] == window]


@router.get("/countries", response_model=list[CountryStats])
def countries(counting: CountingMethod = "fractional") -> list[CountryStats]:
    return []


@router.get("/countries/collaborations", response_model=list[Collaboration])
def collaborations(counting: CountingMethod = "fractional") -> list[Collaboration]:
    return []


@router.get("/countries/{code}", response_model=CountryStats)
def country(code: str) -> CountryStats:
    raise HTTPException(404, "country not found")


@router.get("/runs", response_model=list[Run])
def runs() -> list[Run]:
    out = []
    for i, r in enumerate(ml.get_miner().runs(), 1):
        started = r.get("started_at") or r["run_date"]
        out.append(Run(id=r.get("id", i), started_at=datetime.fromisoformat(started),
                       finished_at=r.get("finished_at"), status=r.get("status", "success"),
                       papers_added=r.get("new_papers", 0),
                       patterns_changed=r.get("patterns_changed", 0)))
    return out
