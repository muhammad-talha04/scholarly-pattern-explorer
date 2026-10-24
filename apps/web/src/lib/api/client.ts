import type {
  AskResponse, AskTurn, ChartScale, Collaboration, CorpusStats, Counting, CountryStats, GalaxyGraph, PaperDetail, PaperSummary,
  Pattern, Run, SearchParams, SearchResponse, TimeGrain, TopicCountryYear, TopicYearQuery,
} from "./types";
import { COUNTRY_AGGREGATE_PATH, COUNTRY_CHART_TOP_N, PUBLICATION_AGGREGATE_PATH, TOPIC_AGGREGATE_PATH, countryChartFromStats, parseCountryChart, parsePublication, parseTopicAggregate } from "@/lib/charts/aggregate";
import * as mock from "./mock";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");
const FORCE_MOCK = process.env.NEXT_PUBLIC_API_MOCK === "1";

/** True when the app is configured to stay on fixtures (no gateway, or the mock flag). */
export function prefersFixtures() { return !API_URL || FORCE_MOCK; }

/** Page size for /search. NEXT_PUBLIC_SEARCH_LIMIT overrides the default of 20. */
export function searchPageSize(): number {
  const raw = Number(process.env.NEXT_PUBLIC_SEARCH_LIMIT);
  if (Number.isFinite(raw) && raw >= 1) return Math.floor(raw);
  return 20;
}

/**
 * Optional cap sent as GET /galaxy?limit=. Unset means the client asks for the
 * whole graph. The API also returns every node unless GALAXY_NODE_LIMIT is set.
 */
export function galaxyNodeLimit(): number | undefined {
  const raw = process.env.NEXT_PUBLIC_GALAXY_LIMIT;
  if (raw == null || raw.trim() === "") return undefined;
  const n = Number(raw);
  if (!Number.isFinite(n) || n < 0) return undefined;
  return Math.floor(n);
}

export type Source = "live" | "mock";
export interface Result<T> { data: T; source: Source }

type Listener = (s: Source) => void;
const listeners = new Set<Listener>();
let lastSource: Source = prefersFixtures() ? "mock" : "live";
export function onSourceChange(fn: Listener) { listeners.add(fn); fn(lastSource); return () => { listeners.delete(fn); }; }
function report(s: Source) { if (s !== lastSource) { lastSource = s; listeners.forEach((l) => l(s)); } }

export class ApiError extends Error { constructor(public status: number, msg: string) { super(msg); } }

const EMPTY_GALAXY: GalaxyGraph = { nodes: [], clusters: [], links: [] };

function finite(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function text(v: unknown): string | null {
  if (typeof v === "string" && v.trim()) return v.trim();
  if (typeof v === "number" && Number.isFinite(v)) return String(v);
  return null;
}

function colorIndex(v: unknown): number | undefined {
  const n = finite(v);
  if (n == null) return undefined;
  return Math.trunc(n);
}

function unitScore(v: unknown): number | undefined {
  const n = finite(v);
  if (n == null) return undefined;
  return Math.min(1, Math.max(0, n));
}

function clusterName(id: string, label: unknown): string {
  const named = text(label);
  if (named) return named;
  const n = Number(id);
  if (Number.isFinite(n) && n < 0) return "unclustered";
  return `cluster ${id}`;
}

/** #8 paper point, or one node of a `{nodes, clusters, links}` graph. */
function pointToNode(row: Record<string, unknown>): GalaxyGraph["nodes"][number] | null {
  const x = finite(row.x), y = finite(row.y), z = finite(row.z);
  const workId = text(row.id);
  const id = workId ?? text(row.topic_id);
  if (x == null || y == null || z == null || !id) return null;
  const cluster_id = text(row.cluster_id) ?? "0";
  const node: GalaxyGraph["nodes"][number] = {
    topic_id: text(row.topic_id) ?? id,
    topic_name: text(row.topic_name) ?? id,
    x, y, z,
    cluster_id,
    support: finite(row.support) ?? 1,
  };
  if (workId) node.id = workId;
  const title = text(row.title);
  if (title) node.title = title;
  const color_index = colorIndex(row.color_index);
  if (color_index !== undefined) node.color_index = color_index;
  return node;
}

function fromPaperList(rows: unknown[]): GalaxyGraph {
  const nodes: GalaxyGraph["nodes"] = [];
  const clusters = new Map<string, string>();
  for (const row of rows) {
    if (!row || typeof row !== "object" || Array.isArray(row)) continue;
    const rec = row as Record<string, unknown>;
    const node = pointToNode(rec);
    if (!node) continue;
    nodes.push(node);
    if (!clusters.has(node.cluster_id)) clusters.set(node.cluster_id, clusterName(node.cluster_id, rec.cluster_label));
  }
  return { nodes, clusters: [...clusters.entries()].map(([id, name]) => ({ id, name })), links: [] };
}

function fromGraph(raw: Record<string, unknown>): GalaxyGraph {
  const nodes: GalaxyGraph["nodes"] = [];
  const rows = raw.nodes as unknown[];
  for (const row of rows) {
    if (!row || typeof row !== "object" || Array.isArray(row)) continue;
    const node = pointToNode(row as Record<string, unknown>);
    if (!node) continue;
    nodes.push(node);
  }
  const clusters: GalaxyGraph["clusters"] = [];
  if (Array.isArray(raw.clusters)) {
    for (const c of raw.clusters) {
      if (!c || typeof c !== "object" || Array.isArray(c)) continue;
      const rec = c as Record<string, unknown>;
      const id = text(rec.id);
      if (!id) continue;
      const cluster: GalaxyGraph["clusters"][number] = { id, name: text(rec.name) ?? id };
      const color_index = colorIndex(rec.color_index);
      const emerging_score = unitScore(rec.emerging_score);
      if (color_index !== undefined) cluster.color_index = color_index;
      if (emerging_score !== undefined) cluster.emerging_score = emerging_score;
      clusters.push(cluster);
    }
  }
  const links: GalaxyGraph["links"] = [];
  if (Array.isArray(raw.links)) {
    for (const link of raw.links) {
      if (!link || typeof link !== "object" || Array.isArray(link)) continue;
      const rec = link as Record<string, unknown>;
      const source = text(rec.source), target = text(rec.target);
      if (!source || !target) continue;
      links.push({ source, target, weight: finite(rec.weight) ?? 1 });
    }
  }
  return { nodes, clusters, links };
}

/**
 * Accepts the topic graph `{nodes, clusters, links}` and the #8 paper list
 * `{id, x, y, z, cluster_id, cluster_label, year}`. Anything else becomes an
 * empty graph so the landing page can show its empty state instead of throwing.
 */
export function normalizeGalaxy(raw: unknown): GalaxyGraph {
  try {
    if (Array.isArray(raw)) return fromPaperList(raw);
    if (raw && typeof raw === "object" && Array.isArray((raw as { nodes?: unknown }).nodes)) {
      return fromGraph(raw as Record<string, unknown>);
    }
  } catch {
    return { ...EMPTY_GALAXY, nodes: [], clusters: [], links: [] };
  }
  return { nodes: [], clusters: [], links: [] };
}

function qs(params: Record<string, string | number | undefined | null>) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : "";
}

export interface RequestOpts {
  notFoundIsMock?: boolean;
  /**
   * 404 or 501 resolves to null and does not flip the nav badge to mock.
   * Used by chart aggregates that are not on the API yet, so a missing route
   * does not paint fixture totals on top of a live corpus.
   */
  notFoundIsEmpty?: boolean;
}

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
  if (opts?.notFoundIsEmpty && (res.status === 404 || res.status === 501)) return { data: null as T, source: "live" };
  if (opts?.notFoundIsMock && res.status === 404) return { data: fallback(), source: "mock" };
  if (res.status === 501) { report("mock"); return { data: fallback(), source: "mock" }; }
  if (!res.ok) throw new ApiError(res.status, `${res.status} ${res.statusText}`);
  report("live");
  return { data: (await res.json()) as T, source: "live" };
}

export const api = {
  health: () => request<{ status: string }>("/health", () => ({ status: "mock" })),
  search: (p: SearchParams) =>
    request<SearchResponse>(`/search${qs({ q: p.q, limit: p.limit, offset: p.offset, country: p.country, year_from: p.year_from })}`, () => mock.search(p)),
  /** Indexed paper count. Fixtures report the sample size, not a live corpus. */
  stats: () => request<CorpusStats>("/stats", () => ({ papers: mock.FIXTURE_COUNT })),
  paper: (id: string) => request<PaperDetail>(`/papers/${encodeURIComponent(id)}`, () => mock.paper(id)),
  ask: (id: string, question: string, history: AskTurn[] = []) =>
    request<AskResponse>(`/papers/${encodeURIComponent(id)}/ask`, () => mock.ask(id, question), { method: "POST", body: JSON.stringify({ question, history }) }),
  related: (id: string, limit = 6) => request<PaperSummary[]>(`/papers/${encodeURIComponent(id)}/related${qs({ limit })}`, () => mock.related(id, limit)),
  patterns: (opts: { window?: number; trend?: "gap" | "emerging" } = {}) =>
    request<Pattern[]>(`/patterns${qs(opts)}`, () => (opts.trend === "gap" ? mock.gaps() : opts.trend === "emerging" ? mock.emerging() : mock.patterns(opts.window))),
  countries: (counting: Counting = "fractional", scale?: ChartScale) =>
    request<CountryStats[]>(`/countries${qs({ counting })}`, () => mock.countries(counting, scale)),
  country: (code: string, counting: Counting = "fractional") =>
    request<CountryStats>(`/countries/${encodeURIComponent(code)}${qs({ counting })}`, () => mock.country(code, counting)),
  collaborations: (counting: Counting = "fractional") =>
    request<Collaboration[]>(`/countries/collaborations${qs({ counting })}`, () => mock.collaborations(counting), undefined, fetch, { notFoundIsMock: true }),
  runs: () => request<Run[]>("/runs", () => mock.runs()),
  /** Paper or topic coordinates. Accepts the #8 list and `{nodes, clusters, links}`. */
  galaxy: async (limit?: number) => {
    const cap = limit ?? galaxyNodeLimit();
    const result = await request<unknown>(`/galaxy${qs({ limit: cap })}`, () => mock.galaxy(cap), undefined, fetch, { notFoundIsMock: true });
    return { data: normalizeGalaxy(result.data), source: result.source };
  },
  /** Topic × country × year rows. Mock until GET /topic-country-years exists (PR #6). */
  topicCountryYears: (q: TopicYearQuery = {}) =>
    request<TopicCountryYear[]>(`/topic-country-years${qs({ topic_id: q.topic_id, country: q.country, year: q.year, limit: q.limit })}`, () => mock.topicCountryYears(q), undefined, fetch, { notFoundIsMock: true }),
  /**
   * Precomputed publication buckets. Each one has `sampled` and `estimated_total`.
   * The chart plots `estimated_total` because the sample is even per month.
   * `scale` is fixture-only and is not sent on the wire.
   * A 404/501 (route not shipped) returns null — the page waits, it does not count rows.
   */
  publications: async (q: { grain?: TimeGrain; year?: number | null; scale?: ChartScale } = {}) => {
    const grain = q.grain ?? "year";
    const result = await request<unknown>(
      `${PUBLICATION_AGGREGATE_PATH}${qs({ grain, year: grain === "month" ? q.year ?? undefined : undefined })}`,
      () => mock.publicationAggregate(q),
      undefined, fetch, { notFoundIsEmpty: true },
    );
    if (result.data == null) return { data: null, source: result.source };
    return { data: parsePublication(result.data), source: result.source };
  },
  /** Precomputed topic shares (percent of that period) for the stream. Same 404 behavior as publications. */
  topicVolume: async (q: { grain?: TimeGrain; year?: number | null; top?: number; scale?: ChartScale } = {}) => {
    const grain = q.grain ?? "year";
    const result = await request<unknown>(
      `${TOPIC_AGGREGATE_PATH}${qs({ grain, year: grain === "month" ? q.year ?? undefined : undefined, top: q.top })}`,
      () => mock.topicVolume(q),
      undefined, fetch, { notFoundIsEmpty: true },
    );
    if (result.data == null) return { data: null, source: result.source };
    return { data: parseTopicAggregate(result.data), source: result.source };
  },
  /**
   * Top-N countries plus an Other bucket, as a percent of the selected period.
   * When the route is missing, the chart folds GET /countries totals (also precomputed) into those shares.
   * It does not fetch topic-country-year rows.
   */
  countryChart: async (q: { counting?: Counting; top?: number; year?: number | null; scale?: ChartScale } = {}) => {
    const counting = q.counting ?? "fractional";
    const top = q.top ?? COUNTRY_CHART_TOP_N;
    const result = await request<unknown>(
      `${COUNTRY_AGGREGATE_PATH}${qs({ counting, top, year: q.year ?? undefined })}`,
      () => mock.countryChart({ ...q, counting, top }),
      undefined, fetch, { notFoundIsEmpty: true },
    );
    if (result.data == null) {
      const cs = await api.countries(counting, q.scale);
      return { data: countryChartFromStats(cs.data, { top, year: q.year, counting }), source: cs.source };
    }
    const parsed = parseCountryChart(result.data);
    return { data: parsed, source: result.source };
  },
};
