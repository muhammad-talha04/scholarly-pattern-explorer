import type {
  AskResponse, Collaboration, Counting, CountryStats, GalaxyGraph, PaperDetail, PaperSummary,
  Pattern, Run, SearchParams, SearchResponse, TopicCountryYear, TopicYearQuery,
} from "./types";
import * as mock from "./mock";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");
const FORCE_MOCK = process.env.NEXT_PUBLIC_API_MOCK === "1";

/** True when the app is configured to stay on fixtures (no gateway, or the mock flag). */
export function prefersFixtures() { return !API_URL || FORCE_MOCK; }

export type Source = "live" | "mock";
export interface Result<T> { data: T; source: Source }

type Listener = (s: Source) => void;
const listeners = new Set<Listener>();
let lastSource: Source = prefersFixtures() ? "mock" : "live";
export function onSourceChange(fn: Listener) { listeners.add(fn); fn(lastSource); return () => { listeners.delete(fn); }; }
function report(s: Source) { if (s !== lastSource) { lastSource = s; listeners.forEach((l) => l(s)); } }

export class ApiError extends Error { constructor(public status: number, msg: string) { super(msg); } }

function qs(params: Record<string, string | number | undefined | null>) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : "";
}

export interface RequestOpts { notFoundIsMock?: boolean }

/**
 * Calls /api/v1{path}. Falls back to the mock when the API is unconfigured,
 * unreachable, or answers 501 (not implemented). A 404 falls back only when
 * `notFoundIsMock` is set, so unfinished routes (galaxy, topic-country-years)
 * keep the UI working and switch to live data as soon as they return 200.
 * Other HTTP errors propagate so the UI can show them.
 */
export async function request<T>(path: string, fallback: () => T, init?: RequestInit, fetcher: typeof fetch = fetch, opts?: RequestOpts): Promise<Result<T>> {
  if (prefersFixtures()) { report("mock"); return { data: fallback(), source: "mock" }; }
  let res: Response;
  try {
    res = await fetcher(`${API_URL}/api/v1${path}`, { ...init, headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) } });
  } catch {
    report("mock"); return { data: fallback(), source: "mock" };
  }
  // A missing optional route (galaxy, topic-country-years) uses fixtures for that
  // call only. It does not flip the nav badge, which tracks the primary API.
  if (opts?.notFoundIsMock && res.status === 404) return { data: fallback(), source: "mock" };
  if (res.status === 501) { report("mock"); return { data: fallback(), source: "mock" }; }
  if (!res.ok) throw new ApiError(res.status, `${res.status} ${res.statusText}`);
  report("live");
  return { data: (await res.json()) as T, source: "live" };
}

export const api = {
  health: () => request<{ status: string }>("/health", () => ({ status: "mock" })),
  search: (p: SearchParams) =>
    request<SearchResponse>(`/search${qs({ q: p.q, limit: p.limit, country: p.country, year_from: p.year_from })}`, () => mock.search(p)),
  paper: (id: string) => request<PaperDetail>(`/papers/${encodeURIComponent(id)}`, () => mock.paper(id)),
  ask: (id: string, question: string) =>
    request<AskResponse>(`/papers/${encodeURIComponent(id)}/ask`, () => mock.ask(id, question), { method: "POST", body: JSON.stringify({ question }) }),
  related: (id: string, limit = 6) => request<PaperSummary[]>(`/papers/${encodeURIComponent(id)}/related${qs({ limit })}`, () => mock.related(id, limit)),
  patterns: (opts: { window?: number; trend?: "gap" } = {}) =>
    request<Pattern[]>(`/patterns${qs(opts)}`, () => (opts.trend === "gap" ? mock.gaps() : mock.patterns(opts.window))),
  countries: (counting: Counting = "fractional") =>
    request<CountryStats[]>(`/countries${qs({ counting })}`, () => mock.countries(counting)),
  country: (code: string, counting: Counting = "fractional") =>
    request<CountryStats>(`/countries/${encodeURIComponent(code)}${qs({ counting })}`, () => mock.country(code, counting)),
  collaborations: (counting: Counting = "fractional") =>
    request<Collaboration[]>(`/countries/collaborations${qs({ counting })}`, () => mock.collaborations(counting), undefined, fetch, { notFoundIsMock: true }),
  runs: () => request<Run[]>("/runs", () => mock.runs()),
  /** 3D topic coordinates and clusters. Mock until GET /galaxy exists. */
  galaxy: () => request<GalaxyGraph>("/galaxy", () => mock.galaxy(), undefined, fetch, { notFoundIsMock: true }),
  /** Topic × country × year rows. Mock until GET /topic-country-years exists (PR #6). */
  topicCountryYears: (q: TopicYearQuery = {}) =>
    request<TopicCountryYear[]>(`/topic-country-years${qs({ topic_id: q.topic_id, country: q.country, year: q.year, limit: q.limit })}`, () => mock.topicCountryYears(q), undefined, fetch, { notFoundIsMock: true }),
};
