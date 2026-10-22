"""Single source of truth for API types. The web client is generated from these."""
from datetime import date, datetime
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
    total: int = 0
    limit: int = 20
    offset: int = 0


class CorpusStats(BaseModel):
    """Indexed papers. This is the corpus size, not a search page."""
    papers: int


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str
    sources: list[str] = []


class ExamplePaper(BaseModel):
    """A paper cited as an illustration on a gap or emerging-topic row."""
    id: str
    title: str = ""
    year: int | None = None
    score: float | None = None


class Pattern(BaseModel):
    items: list[str]
    support: float
    window_start: int
    window_end: int
    # Optional, filled for trend=gap and trend=emerging.
    gap_score: float | None = None
    growth_rate: float | None = None
    paper_count: int | None = None
    top_countries: list[str] | None = None
    explanation: str | None = None
    example_papers: list[ExamplePaper] | None = None


class CountryYearCount(BaseModel):
    year: int
    paper_count: int
    fractional_count: float


class CountryStats(BaseModel):
    code: str
    name: str
    papers: float  # value for `counting`; fractional counts are not integers
    # Equal-period growth: Jan 1..newest publication date vs the same dates a year earlier.
    growth_pct: float | None = None
    growth_reason: Literal["too_few_papers", "partial_year"] | None = None
    growth_cur_count: float | None = None
    growth_prev_count: float | None = None
    growth_window_start: date | None = None
    growth_window_end: date | None = None
    # Share of corpus in the same window (percent of all papers; change in percentage points)
    share_pct: float | None = None
    share_prev_pct: float | None = None
    share_change_pp: float | None = None
    share_reason: Literal["too_few_papers", "partial_year"] | None = None
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


class GalaxyCentroid(BaseModel):
    x: float
    y: float
    z: float


class GalaxyCluster(BaseModel):
    """One topic cluster. ``name`` is the front-end label; ``label`` is the same string."""
    id: str
    name: str
    label: str
    centroid: GalaxyCentroid
    size: int


class GalaxyNode(BaseModel):
    """One paper. Links join on ``id`` (the work id).

    ``title`` is the paper title. ``topic_name`` is the OpenAlex display name.
    ``title`` defaults to empty so a galaxy document stored before that split
    still validates; the client then keeps the older title-keyed links.
    """
    id: str
    topic_id: str
    topic_name: str
    title: str = ""
    x: float
    y: float
    z: float
    cluster_id: str
    cluster_label: str = ""
    year: int | None = None
    support: float


class GalaxyLink(BaseModel):
    source: str
    target: str
    weight: float


class GalaxyGraph(BaseModel):
    """Matches the web client's GalaxyGraph: nodes, clusters, and nearest-neighbour links.

    ``(x, y)`` is the 2D layout; ``(x, y, z)`` is the 3D layout of the same basis.
    """
    nodes: list[GalaxyNode] = []
    clusters: list[GalaxyCluster] = []
    links: list[GalaxyLink] = []
