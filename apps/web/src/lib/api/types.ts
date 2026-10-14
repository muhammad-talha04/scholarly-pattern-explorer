/**
 * Mirrors apps/api/app/schemas.py (single source of truth). Keep in sync, or
 * regenerate from /api/v1/openapi.json once the API is deployed.
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
export interface CountryStats {
  code: string;
  name: string;
  papers: number;
  growth_pct: number | null;
  top_topics: string[];
}
export interface Run {
  id: number;
  started_at: string;
  finished_at: string | null;
  status: string;
  papers_added: number;
  patterns_changed: number;
}

/* ---- Provisional: not yet in schemas.py (grok is adding these routes). ---- */
export type Counting = "fractional" | "full";
export interface Collaboration { source: string; target: string; papers: number }

export interface SearchParams { q: string; limit?: number; country?: string; year_from?: number }
