import type {
  AskResponse, Collaboration, Counting, CountryStats, PaperDetail, PaperSummary,
  Pattern, Run, SearchParams, SearchResponse,
} from "./types";
import * as mock from "./mock";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");
const FORCE_MOCK = process.env.NEXT_PUBLIC_API_MOCK === "1";

export type Source = "live" | "mock";
export interface Result<T> { data: T; source: Source }

type Listener = (s: Source) => void;
const listeners = new Set<Listener>();
let lastSource: Source = API_URL && !FORCE_MOCK ? "live" : "mock";
export function onSourceChange(fn: Listener) { listeners.add(fn); fn(lastSource); return () => { listeners.delete(fn); }; }
function report(s: Source) { if (s !== lastSource) { lastSource = s; listeners.forEach((l) => l(s)); } }

export class ApiError extends Error { constructor(public status: number, msg: string) { super(msg); } }

function qs(params: Record<string, string | number | undefined | null>) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : "";
}

/**
 * Calls /api/v1{path}. Falls back to the mock when the API is unconfigured,
 * unreachable, or answers 501 (not implemented). Other HTTP errors (e.g. 404)
 * propagate so the UI can show them.
 */
export async function request<T>(path: string, fallback: () => T, init?: RequestInit, fetcher: typeof fetch = fetch): Promise<Result<T>> {
  if (!API_URL || FORCE_MOCK) { report("mock"); return { data: fallback(), source: "mock" }; }
  let res: Response;
  try {
    res = await fetcher(`${API_URL}/api/v1${path}`, { ...init, headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) } });
  } catch {
    report("mock"); return { data: fallback(), source: "mock" };
  }
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
  countries: async (counting: Counting = "fractional") => {
    const r = await request<CountryStats[]>(`/countries${qs({ counting })}`, () => mock.countries(counting));
    // The current stub returns []; treat an empty live answer as "not ready yet".
    return r.source === "live" && r.data.length === 0 ? { data: mock.countries(counting), source: "mock" as Source } : r;
  },
  country: (code: string) => request<CountryStats>(`/countries/${encodeURIComponent(code)}`, () => mock.country(code)),
  collaborations: async () => {
    try { return await request<Collaboration[]>("/countries/collaborations", () => mock.collaborations()); }
    catch (e) { if (e instanceof ApiError && e.status === 404) return { data: mock.collaborations(), source: "mock" as Source }; throw e; }
  },
  runs: () => request<Run[]>("/runs", () => mock.runs()),
};
