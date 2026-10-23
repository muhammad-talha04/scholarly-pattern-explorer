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
 * Largest-remainder percents to 0.1. The parts sum to 100 when any weight is positive.
 * Integer tenths (summing to 1000) avoid a 99.9 / 100.1 drift.
 */
export function percentShares(weights: number[]): number[] {
  if (!weights.length) return [];
  const sum = weights.reduce((s, w) => s + Math.max(0, w), 0);
  if (sum <= 0) return weights.map(() => 0);
  const raw = weights.map((w) => (1000 * Math.max(0, w)) / sum);
  const floors = raw.map((n) => Math.floor(n));
  let left = 1000 - floors.reduce((s, n) => s + n, 0);
  const order = raw
    .map((n, i) => [n - floors[i], i] as const)
    .sort((a, b) => b[0] - a[0] || a[1] - b[1]);
  for (let k = 0; left > 0; k++, left--) floors[order[k % order.length][1]] += 1;
  return floors.map((t) => t / 10);
}

/**
 * Top-N chart from country totals the API already summed.
 * Shares are the percent of this selection. This does not count papers or topic-country-year cells.
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
  const named = valued.slice(0, Math.max(0, top));
  const rest = valued.slice(Math.max(0, top));
  const otherPapers = rest.reduce((s, c) => s + c.papers, 0);
  const weights = named.map((c) => c.papers);
  if (rest.length) weights.push(otherPapers);
  const shares = percentShares(weights);
  const items = named.map((c, i) => ({ code: c.code, name: c.name, share: shares[i] ?? 0 }));
  const other = rest.length ? { share: shares[shares.length - 1] ?? 0, countries: rest.length } : null;
  return { counting, year, top, items, other };
}

/** Insert every calendar month the payload left out. A missing month is unknown (null), not a measured zero. */
export function fillMonthBuckets(year: number, buckets: TimeBucket[]): TimeBucket[] {
  const by = new Map(buckets.map((b) => [b.key, b]));
  return monthKeys(year).map((key) => {
    const hit = by.get(key);
    return hit
      ? { key, sampled: hit.sampled, estimated_total: hit.estimated_total }
      : { key, sampled: 0, estimated_total: null };
  });
}

/**
 * Sum of known OpenAlex totals. Null when a bucket we sampled has no rate, and
 * null when every bucket is unknown. Empty months with a null estimate do not
 * blank out the months that do have a rate.
 */
export function rollupEstimate(buckets: { sampled: number; estimated_total: number | null }[]): number | null {
  if (!buckets.length || buckets.every((b) => b.estimated_total == null)) return null;
  if (buckets.some((b) => b.sampled > 0 && b.estimated_total == null)) return null;
  return buckets.reduce((s, b) => s + (b.estimated_total ?? 0), 0);
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
    return { name: s.name, keys, years, values: s.points.map((p) => p.share) };
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
    const by = new Map(s.points.map((p) => [p.key, p.share]));
    return { name: s.name, points: keys.map((key) => ({ key, share: by.get(key) ?? 0 })) };
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
    const sampled = num(row.sampled) ?? num(row.paper_count);
    const estimated_total = row.estimated_total == null ? null : num(row.estimated_total);
    if (!key || sampled == null || sampled < 0 || (estimated_total != null && estimated_total < 0)) continue;
    buckets.push({ key, sampled, estimated_total });
  }
  const year = num(rec.year);
  const normalized = normalizePublication({ grain, year: year == null ? null : year, sampled: 0, estimated_total: null, buckets });
  return {
    ...normalized,
    sampled: normalized.buckets.reduce((s, b) => s + b.sampled, 0),
    estimated_total: rollupEstimate(normalized.buckets),
  };
}

export function parseTopicAggregate(raw: unknown): TopicAggregate | null {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const rec = raw as Record<string, unknown>;
  const grain: TimeGrain | null = rec.grain === "month" || rec.grain === "year" ? rec.grain : null;
  if (!grain || !Array.isArray(rec.series)) return null;
  const periodSampled = new Map<string, number>();
  if (Array.isArray(rec.period)) {
    for (const row of rec.period) {
      if (!row || typeof row !== "object" || Array.isArray(row)) continue;
      const period = row as Record<string, unknown>;
      const key = text(period.key);
      const sampled = num(period.sampled);
      if (key && sampled != null && sampled >= 0) periodSampled.set(key, sampled);
    }
  }
  const series: TopicAggregateSeries[] = [];
  const pending: { name: string; points: { key: string; share: number | null; value: number | null }[] }[] = [];
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
      if (!key) continue;
      const share = num(pt.share);
      const value = num(pt.value);
      if ((share == null || share < 0) && (value == null || value < 0)) continue;
      points.push({
        key,
        share: share != null && share >= 0 ? share : null,
        value: value != null && value >= 0 ? value : null,
      });
    }
    pending.push({ name, points });
  }
  const columnValue = new Map<string, number>();
  for (const s of pending) {
    for (const p of s.points) {
      if (p.share == null && p.value != null) columnValue.set(p.key, (columnValue.get(p.key) ?? 0) + p.value);
    }
  }
  for (const s of pending) {
    series.push({
      name: s.name,
      points: s.points.map((p) => {
        if (p.share != null) return { key: p.key, share: p.share };
        const denom = periodSampled.get(p.key) ?? columnValue.get(p.key) ?? 0;
        const share = denom > 0 && p.value != null ? (p.value / denom) * 100 : 0;
        return { key: p.key, share };
      }),
    });
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
  const rawItems: { code: string; name: string; share: number | null; papers: number | null }[] = [];
  for (const item of rec.items) {
    if (!item || typeof item !== "object" || Array.isArray(item)) continue;
    const row = item as Record<string, unknown>;
    const code = text(row.code);
    const name = text(row.name);
    if (!code || !name) continue;
    const share = num(row.share);
    const papers = num(row.papers);
    if ((share == null || share < 0) && (papers == null || papers < 0)) continue;
    rawItems.push({
      code,
      name,
      share: share != null && share >= 0 ? share : null,
      papers: papers != null && papers >= 0 ? papers : null,
    });
  }
  let otherShare: number | null = null;
  let otherPapers: number | null = null;
  let otherCountries: number | null = null;
  if (rec.other && typeof rec.other === "object" && !Array.isArray(rec.other)) {
    const o = rec.other as Record<string, unknown>;
    const share = num(o.share);
    const papers = num(o.papers);
    const countries = num(o.countries);
    if (share != null && share >= 0) otherShare = share;
    if (papers != null && papers >= 0) otherPapers = papers;
    if (countries != null && countries > 0) otherCountries = countries;
  }
  const sentShares = rawItems.some((item) => item.share != null) || otherShare != null;
  let items: CountryChart["items"];
  let other: CountryChart["other"] = null;
  if (sentShares) {
    items = rawItems.filter((item) => item.share != null).map((item) => ({ code: item.code, name: item.name, share: item.share as number }));
    if (otherShare != null && otherCountries != null) other = { share: otherShare, countries: otherCountries };
  } else {
    const counted = rawItems.filter((item): item is { code: string; name: string; share: number | null; papers: number } => item.papers != null);
    const weights = counted.map((item) => item.papers);
    if (otherPapers != null && otherCountries != null) weights.push(otherPapers);
    const shares = percentShares(weights);
    items = counted.map((item, i) => ({ code: item.code, name: item.name, share: shares[i] ?? 0 }));
    if (otherPapers != null && otherCountries != null) other = { share: shares[shares.length - 1] ?? 0, countries: otherCountries };
  }
  const year = num(rec.year);
  const top = num(rec.top) ?? items.length;
  return { counting, year: year == null ? null : year, top, items, other };
}
