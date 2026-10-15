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
export interface SearchResponse { query: string; results: PaperSummary[] }
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
export interface CountryStats {
  code: string;
  name: string;
  papers: number;
  growth_pct: number | null;
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

export interface GalaxyCluster { id: string; name: string }
/** A topic placed in 3D, plus the cluster it belongs to (GET /galaxy). */
export interface GalaxyPoint {
  topic_id: string;
  topic_name: string;
  x: number;
  y: number;
  z: number;
  cluster_id: string;
  support: number;
}
export interface GalaxyGraph {
  nodes: GalaxyPoint[];
  clusters: GalaxyCluster[];
  links: { source: string; target: string; weight: number }[];
}

export interface SearchParams { q: string; limit?: number; country?: string; year_from?: number }
export interface TopicYearQuery { topic_id?: string; country?: string; year?: number; limit?: number }
