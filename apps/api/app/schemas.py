"""Single source of truth for API types. The web client is generated from these."""
from datetime import datetime
from pydantic import BaseModel, HttpUrl


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
    papers: int
    growth_pct: float | None = None
    top_topics: list[str] = []


class Run(BaseModel):
    id: int
    started_at: datetime
    finished_at: datetime | None = None
    status: str
    papers_added: int = 0
    patterns_changed: int = 0
