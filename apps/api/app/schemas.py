"""Single source of truth for API types. The web client is generated from these."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, HttpUrl

CountingMethod = Literal["fractional", "full"]


class PaperSummary(BaseModel):
    id: str
    title: str
    authors: list[str] = []
    year: int | None = None
    cited_by: int = 0
    one_line_summary: str | None = None
    score: float | None = None


class PaperDetail(PaperSummary):
    abstract: str | None = None
    summary: str | None = None
    topics: list[str] = []
    countries: list[str] = []
    original_url: HttpUrl | None = None
    openalex_url: HttpUrl | None = None


class SearchResponse(BaseModel):
    query: str
    results: list[PaperSummary]


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str
    sources: list[str] = []


class Pattern(BaseModel):
    items: list[str]
    support: float
    window_start: int
    window_end: int


class CountryStats(BaseModel):
    code: str
    name: str
    papers: float  # fractional counts by default
    growth_pct: float | None = None
    top_topics: list[str] = []
    counting: CountingMethod = "fractional"


class Run(BaseModel):
    id: int
    started_at: datetime
    finished_at: datetime | None = None
    status: str
    papers_added: int = 0
    patterns_changed: int = 0


class Collaboration(BaseModel):
    source: str   # ISO 3166 alpha-2
    target: str
    papers: float  # fractional or full, per the request's counting method
