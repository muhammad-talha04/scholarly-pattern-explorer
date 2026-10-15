"""Single source of truth for API types. The web client is generated from these."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, HttpUrl

CountingMethod = Literal["fractional", "per_country", "full"]


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
    # Optional, filled only for trend=gap (research-gap finder, ml/gaps.py).
    gap_score: float | None = None
    growth_rate: float | None = None
    paper_count: int | None = None
    top_countries: list[str] | None = None


class CountryYearCount(BaseModel):
    year: int
    paper_count: int
    fractional_count: float


class CountryStats(BaseModel):
    code: str
    name: str
    papers: float  # value for `counting`; fractional counts are not integers
    growth_pct: float | None = None
    top_topics: list[str] = []
    counting: CountingMethod = "fractional"
    paper_count: int = 0            # whole papers, every country on the paper counted once
    fractional_count: float = 0     # sum of 1/N over distinct countries
    by_year: list[CountryYearCount] = []


class TopicCountryYear(BaseModel):
    """One row of the topic × country × year aggregate."""
    topic_id: str
    topic_name: str
    country_code: str
    year: int
    paper_count: int
    fractional_count: float


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


class GalaxyPoint(BaseModel):
    """One paper in the galaxy. (x, y) is the 2D layout; (x, y, z) is the 3D layout."""
    id: str
    x: float
    y: float
    z: float
    cluster_id: int
    cluster_label: str = ""
    year: int | None = None
