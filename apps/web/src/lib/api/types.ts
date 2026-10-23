/**
 * Mirrors apps/api/app/schemas.py (single source of truth). Keep in sync, or
 * regenerate from /api/v1/openapi.json once the API is deployed.
 *
 * GalaxyGraph is what the scene renders. GET /galaxy may return that object,
 * or the #8 paper list (id, x, y, z, cluster_id, cluster_label, year).
 * `normalizeGalaxy` in client.ts turns either one into GalaxyGraph.
 * `/topic-country-years` matches the #6 table and is live on main.
 */
export interface PaperSummary {
  id: string;
  title: string;
  authors: string[];
  year: number | null;
  cited_by: number;
  one_line_summary: string | null;
  score: number | null;
}
export interface PaperDetail extends PaperSummary {
  abstract: string | null;
  summary: string | null;
  topics: string[];
  countries: string[];
  original_url: string | null;
  openalex_url: string | null;
}
export interface SearchResponse {
  query: string;
  results: PaperSummary[];
  /** Ranked hits in this window. Omitted by older APIs. */
  total?: number;
  limit?: number;
  offset?: number;
}
export interface CorpusStats { papers: number }
export interface AskRequest { question: string }
export interface AskResponse { answer: string; sources: string[] }
export interface Pattern {
  items: string[];
  support: number;
  window_start: number;
  window_end: number;
  gap_score?: number | null;
  growth_rate?: number | null;
  paper_count?: number | null;
  top_countries?: string[] | null;
}
export interface CountryYearCount {
  year: number;
  paper_count: number;
  fractional_count: number;
}
export type GrowthReason = "too_few_papers" | "partial_year";

export interface CountryStats {
  code: string;
  name: string;
  papers: number;
  growth_pct: number | null;
  /** Optional growth details (country_stats growth spec). Older snapshots omit them. */
  growth_reason?: GrowthReason | null;
  growth_cur_count?: number | null;
  growth_prev_count?: number | null;
  /** ISO dates (YYYY-MM-DD) for the current window; the previous window is the same span one year earlier. */
  growth_window_start?: string | null;
  growth_window_end?: string | null;
  /** Optional share-of-papers fields. Same windows and counts as growth; share_reason is separate from growth_reason. */
  share_pct?: number | null;
  share_prev_pct?: number | null;
  share_change_pp?: number | null;
  share_reason?: GrowthReason | null;
  top_topics: string[];
  /** Present once the live snapshot includes it (PR #6). */
  counting?: Counting;
  paper_count?: number;
  fractional_count?: number;
  by_year?: CountryYearCount[];
}
export interface Run {
  id: number;
  started_at: string;
  finished_at: string | null;
  status: string;
  papers_added: number;
  patterns_changed: number;
}

export type Counting = "fractional" | "per_country" | "full";
export interface Collaboration { source: string; target: string; papers: number }

/** One row of the topic × country × year table (GET /topic-country-years). */
export interface TopicCountryYear {
  topic_id: string;
  topic_name: string;
  country_code: string;
  year: number;
  paper_count: number;
  fractional_count: number;
}

export interface GalaxyCluster {
  id: string;
  name: string;
  /** Optional 0-based swatch. Missing means the client derives one from the id. */
  color_index?: number;
  /** Optional 0–1 warmth from /galaxy. Missing means the cluster does not glow warmer. */
  emerging_score?: number;
}
/** One paper in the galaxy. `topic_name` is the label; `cluster_id` is its topic cluster. */
export interface GalaxyPoint {
  topic_id: string;
  topic_name: string;
  x: number;
  y: number;
  z: number;
  cluster_id: string;
  support: number;
  color_index?: number;
}
export interface GalaxyGraph {
  nodes: GalaxyPoint[];
  clusters: GalaxyCluster[];
  links: { source: string; target: string; weight: number }[];
}

export interface SearchParams { q: string; limit?: number; offset?: number; country?: string; year_from?: number }
export interface TopicYearQuery { topic_id?: string; country?: string; year?: number; limit?: number }

/**
 * Chart aggregates. Not in schemas.py yet — the API owner (lura) still needs
 * to serve these. Shapes the web client already reads:
 *
 * GET /api/v1/aggregates/publications?grain=year|month&year=
 *   { grain, year, total, buckets: [{ key, paper_count }] }
 *   key is "2025" or "2025-03". Month responses include every month, zeros included.
 *
 * GET /api/v1/aggregates/topics?grain=year|month&year=&top=
 *   { grain, year, top, series: [{ name, points: [{ key, value }] }] }
 *   values are already summed. "Other" is a series when the tail was folded in.
 *
 * GET /api/v1/aggregates/countries?counting=&top=&year=
 *   { counting, year, top, total, items: [{ code, name, papers }], other: { papers, countries } | null }
 */
export type TimeGrain = "year" | "month";
/** Fixture-only preview. Never sent to a live API. */
export type ChartScale = "sample" | "80k";

export interface TimeBucket {
  /** "2025" or "2025-03". */
  key: string;
  paper_count: number;
}
export interface PublicationAggregate {
  grain: TimeGrain;
  year: number | null;
  /** Papers in this response, already summed. */
  total: number;
  buckets: TimeBucket[];
}
export interface TopicPoint { key: string; value: number }
export interface TopicAggregateSeries { name: string; points: TopicPoint[] }
export interface TopicAggregate {
  grain: TimeGrain;
  year: number | null;
  top: number;
  series: TopicAggregateSeries[];
}
export interface CountryChartItem { code: string; name: string; papers: number }
export interface CountryChart {
  counting: Counting;
  year: number | null;
  top: number;
  total: number;
  items: CountryChartItem[];
  /** Null when every country is already named in items. */
  other: { papers: number; countries: number } | null;
}
