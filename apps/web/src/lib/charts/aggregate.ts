import type { Counting, CountryChart, CountryStats, PublicationAggregate, TimeBucket, TimeGrain, TopicAggregate, TopicAggregateSeries } from "@/lib/api/types";
import type { TopicSeries } from "@/lib/series";
import { monthKeys } from "./axis";

/** How many countries stay named on the bar chart. The rest fold into Other. */
export const COUNTRY_CHART_TOP_N = 12;

/**
 * Routes the charts call. These are not on the API yet — see the note on each
 * client method. Responses are precomputed totals, never paper rows.
 */
export const PUBLICATION_AGGREGATE_PATH = "/aggregates/publications";
export const TOPIC_AGGREGATE_PATH = "/aggregates/topics";
export const COUNTRY_AGGREGATE_PATH = "/aggregates/countries";

export function papersInYear(c: CountryStats, year: number, counting: Counting): number {
  const row = c.by_year?.find((y) => y.year === year);
  if (!row) return 0;
  return counting === "full" ? row.paper_count : row.fractional_count;
}

export function yearRangeFromCountries(rows: CountryStats[]): [number, number] | null {
  let min = Infinity, max = -Infinity;
  for (const c of rows) {
    for (const y of c.by_year ?? []) {
      if (y.year < min) min = y.year;
      if (y.year > max) max = y.year;
    }
  }
  if (!Number.isFinite(min)) return null;
  return [min, max];
}

/**
 * Top-N chart from country totals the API already summed.
 * `papers` is read as-is. This does not count papers or topic-country-year cells.
 */
export function countryChartFromStats(rows: CountryStats[], opts: { top?: number; year?: number | null; counting?: Counting } = {}): CountryChart {
  const top = opts.top ?? COUNTRY_CHART_TOP_N;
  const counting = opts.counting ?? rows[0]?.counting ?? "fractional";
  const year = opts.year ?? null;
  const valued = rows.map((c) => ({
    code: c.code,
    name: c.name,
    papers: year == null ? c.papers : papersInYear(c, year, counting),
  })).filter((c) => c.papers > 0);
  valued.sort((a, b) => b.papers - a.papers || a.code.localeCompare(b.code));
  const items = valued.slice(0, Math.max(0, top));
  const rest = valued.slice(Math.max(0, top));
  const other = rest.length
    ? { papers: rest.reduce((s, c) => s + c.papers, 0), countries: rest.length }
    : null;
  const total = items.reduce((s, c) => s + c.papers, 0) + (other?.papers ?? 0);
  return { counting, year, top, total, items, other };
}

/** Insert a zero bucket for every calendar month the payload left out. Does not drop months that are already zero. */
export function fillMonthBuckets(year: number, buckets: TimeBucket[]): TimeBucket[] {
  const by = new Map(buckets.map((b) => [b.key, b.paper_count]));
  return monthKeys(year).map((key) => ({ key, paper_count: by.get(key) ?? 0 }));
}

export function normalizePublication(agg: PublicationAggregate): PublicationAggregate {
  const buckets = [...agg.buckets].sort((a, b) => a.key.localeCompare(b.key));
  if (agg.grain !== "month") return { ...agg, year: null, buckets };
  const year = agg.year ?? Number(buckets[0]?.key.slice(0, 4));
  if (!Number.isInteger(year)) return { ...agg, buckets };
  return { ...agg, year, buckets: fillMonthBuckets(year, buckets) };
}

export function seriesFromTopicAggregate(agg: TopicAggregate): TopicSeries[] {
  return agg.series.map((s) => {
    const keys = s.points.map((p) => p.key);
    const years = keys.map((k) => {
      const y = Number(k.slice(0, 4));
      return Number.isFinite(y) ? y : 0;
    });
    return { name: s.name, keys, years, values: s.points.map((p) => p.value) };
  });
}

/** Month grain: every series gets all 12 months, missing ones as 0, in calendar order. */
export function completeTopicAggregate(agg: TopicAggregate): TopicAggregate {
  if (agg.grain !== "month" || agg.year == null) {
    const series = agg.series.map((s) => ({
      name: s.name,
      points: [...s.points].sort((a, b) => a.key.localeCompare(b.key)),
    }));
    return { ...agg, series };
  }
  const keys = monthKeys(agg.year);
  const series: TopicAggregateSeries[] = agg.series.map((s) => {
    const by = new Map(s.points.map((p) => [p.key, p.value]));
    return { name: s.name, points: keys.map((key) => ({ key, value: by.get(key) ?? 0 })) };
  });
  return { ...agg, series };
}

function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function text(v: unknown): string | null {
  return typeof v === "string" && v.trim() ? v.trim() : null;
}

export function parsePublication(raw: unknown): PublicationAggregate | null {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const rec = raw as Record<string, unknown>;
  const grain: TimeGrain | null = rec.grain === "month" || rec.grain === "year" ? rec.grain : null;
  if (!grain || !Array.isArray(rec.buckets)) return null;
  const buckets: TimeBucket[] = [];
  for (const b of rec.buckets) {
    if (!b || typeof b !== "object" || Array.isArray(b)) continue;
    const row = b as Record<string, unknown>;
    const key = text(row.key);
    const paper_count = num(row.paper_count);
    if (!key || paper_count == null || paper_count < 0) continue;
    buckets.push({ key, paper_count });
  }
  const year = num(rec.year);
  const summed = buckets.reduce((s, b) => s + b.paper_count, 0);
  const total = num(rec.total) ?? summed;
  return normalizePublication({ grain, year: year == null ? null : year, total, buckets });
}

export function parseTopicAggregate(raw: unknown): TopicAggregate | null {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const rec = raw as Record<string, unknown>;
  const grain: TimeGrain | null = rec.grain === "month" || rec.grain === "year" ? rec.grain : null;
  if (!grain || !Array.isArray(rec.series)) return null;
  const series: TopicAggregateSeries[] = [];
  for (const s of rec.series) {
    if (!s || typeof s !== "object" || Array.isArray(s)) continue;
    const row = s as Record<string, unknown>;
    const name = text(row.name);
    if (!name || !Array.isArray(row.points)) continue;
    const points = [];
    for (const p of row.points) {
      if (!p || typeof p !== "object" || Array.isArray(p)) continue;
      const pt = p as Record<string, unknown>;
      const key = text(pt.key);
      const value = num(pt.value);
      if (!key || value == null || value < 0) continue;
      points.push({ key, value });
    }
    series.push({ name, points });
  }
  const year = num(rec.year);
  const top = num(rec.top);
  return completeTopicAggregate({
    grain,
    year: year == null ? null : year,
    top: top == null ? series.length : top,
    series,
  });
}

export function parseCountryChart(raw: unknown): CountryChart | null {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const rec = raw as Record<string, unknown>;
  if (!Array.isArray(rec.items)) return null;
  const counting: Counting = rec.counting === "full" || rec.counting === "per_country" || rec.counting === "fractional"
    ? rec.counting
    : "fractional";
  const items = [];
  for (const item of rec.items) {
    if (!item || typeof item !== "object" || Array.isArray(item)) continue;
    const row = item as Record<string, unknown>;
    const code = text(row.code);
    const name = text(row.name);
    const papers = num(row.papers);
    if (!code || !name || papers == null || papers < 0) continue;
    items.push({ code, name, papers });
  }
  let other: CountryChart["other"] = null;
  if (rec.other && typeof rec.other === "object" && !Array.isArray(rec.other)) {
    const o = rec.other as Record<string, unknown>;
    const papers = num(o.papers);
    const countries = num(o.countries);
    if (papers != null && papers >= 0 && countries != null && countries > 0) {
      other = { papers, countries };
    }
  }
  const year = num(rec.year);
  const top = num(rec.top) ?? items.length;
  const total = num(rec.total) ?? items.reduce((s, c) => s + c.papers, 0) + (other?.papers ?? 0);
  return { counting, year: year == null ? null : year, top, total, items, other };
}
