"""Contract routes. Bodies are wired to the ML package (ml/) via app.ml_bridge."""
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from .. import ml_bridge as ml
from pipeline import country_api  # repo root is on sys.path via ml_bridge
from ..schemas import (AskRequest, AskResponse, Collaboration, CountingMethod, CountryStats, ExamplePaper,
                       GalaxyGraph, PaperDetail, PaperSummary, Pattern, Run, SearchResponse,
                       TopicCountryYear)

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


@router.get("/papers/{paper_id}/similar", response_model=list[PaperSummary])
def similar(paper_id: str, limit: int = 10) -> list[PaperSummary]:
    """Papers like this one. ``score`` is cosine similarity in the embedding index."""
    hits = ml.get_service().similar(paper_id, k=max(1, min(limit, 50)))
    if hits is None:
        raise HTTPException(404, "paper not found")
    return [_summary_model(h) for h in hits]


def _example_models(raw) -> list[ExamplePaper] | None:
    out = []
    for row in raw or []:
        if not row or not row.get("id"):
            continue
        year = row.get("year")
        try:
            year = int(year) if year is not None else None
        except (TypeError, ValueError):
            year = None
        out.append(ExamplePaper(id=str(row["id"]), title=row.get("title") or "",
                                year=year, score=row.get("score")))
    return out or None


def _gap_pattern(g: dict) -> Pattern:
    if g.get("items"):
        items = [str(x) for x in g["items"]]
    else:
        items = [str(g["topic"])]
    examples = g.get("example_papers")
    if not examples:
        examples = ml.gap_examples(items)
    explanation = g.get("explanation")
    if not explanation and g.get("growth_rate") is not None and g.get("topic") and not g.get("items"):
        explanation = ml.growth_explanation(g)
    return Pattern(
        items=items, support=g["gap_score"], window_start=g["window_start"],
        window_end=g["window_end"], gap_score=g["gap_score"], growth_rate=g.get("growth_rate"),
        paper_count=g.get("paper_count"), top_countries=g.get("top_countries"),
        explanation=explanation, example_papers=_example_models(examples))


def _in_window(g: dict, window: int | None) -> bool:
    return window is None or g.get("window_start") == window


@router.get("/patterns", response_model=list[Pattern])
def patterns(window: int | None = None, trend: str | None = None,
             country: str | None = None) -> list[Pattern]:
    if trend == "gap":
        # Growing-but-small topics, plus embedding-space gaps (thin regions and
        # related topics that rarely co-occur). Growth rows keep their score so
        # a perfect growth gap stays ahead of an embedding gap with the same score.
        growth = [g for g in ml.get_gaps() if _in_window(g, window)]
        semantic = [g for g in ml.get_semantic_gaps() if _in_window(g, window)][:10]
        merged = sorted(growth + semantic, key=lambda g: (
            -float(g.get("gap_score") or 0),
            0 if g.get("kind", "growth") == "growth" else 1,
            -float(g.get("growth_rate") or 0),
            " ".join(g.get("items") or [g.get("topic") or ""]),
        ))
        return [_gap_pattern(g) for g in merged]
    if trend == "emerging":
        rows = ml.get_emerging(country=country)
        out = []
        for row in rows:
            if not _in_window(row, window):
                continue
            examples = ml.gap_examples([row["topic_name"]])
            out.append(Pattern(
                items=[row["topic_name"]], support=row["growth_score"],
                window_start=row["window_start"], window_end=row["window_end"],
                growth_rate=row["growth_rate"], paper_count=row["paper_count"],
                explanation=row["explanation"], example_papers=_example_models(examples)))
        return out
    rows = ml.get_miner().patterns()
    return [Pattern(items=r["itemset"].split(" | "), support=r["support"],
                    window_start=r["window_start"], window_end=r["window_end"])
            for r in rows if window is None or r["window_start"] == window]


@router.get("/countries", response_model=list[CountryStats])
def countries(counting: CountingMethod = "fractional") -> list[CountryStats]:
    return [CountryStats(**r) for r in country_api.countries(counting)]


@router.get("/countries/collaborations", response_model=list[Collaboration])
def collaborations(counting: CountingMethod = "fractional", limit: int = 200) -> list[Collaboration]:
    rows = country_api.collaborations(counting, limit)
    return [Collaboration(**r) for r in rows[:limit]]


@router.get("/countries/{code}", response_model=CountryStats)
def country(code: str, counting: CountingMethod = "fractional") -> CountryStats:
    r = country_api.country(code, counting)
    if r is None:
        raise HTTPException(404, "country not found")
    return CountryStats(**r)


@router.get("/galaxy", response_model=GalaxyGraph)
def galaxy() -> GalaxyGraph:
    """Stored galaxy graph. The index job precomputes it; this route only reads it."""
    return GalaxyGraph(**ml.get_service().read_galaxy())


@router.get("/topic-country-years", response_model=list[TopicCountryYear])
def topic_country_years(topic_id: str | None = None, country: str | None = None,
                        year: int | None = None, limit: int = 1000) -> list[TopicCountryYear]:
    return country_api.topic_country_years(topic_id, country, year, limit)


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
