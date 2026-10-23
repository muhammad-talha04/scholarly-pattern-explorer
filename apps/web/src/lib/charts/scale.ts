import type { ChartScale, Counting, CountryStats, PublicationAggregate, TimeGrain, TopicAggregate } from "@/lib/api/types";
import { distribute, monthKey } from "./axis";

export type { ChartScale };

/**
 * Months forced to zero so the axis has to keep a real gap.
 * 2024 Jan–Sep: the live corpus starts mid-October 2024.
 * 2015 Jan–Sep: a sparse first year once the window reaches back.
 * 2020 April: a hole in the middle of a year.
 * 2026 Nov–Dec: not published yet (the clock in this repo is October 2026).
 */
export function monthWeights(year: number): number[] {
  const w = [8, 7, 9, 8, 10, 9, 8, 9, 11, 12, 10, 9];
  const zero = new Set<number>();
  if (year === 2015 || year === 2024) for (let m = 0; m < 9; m++) zero.add(m);
  if (year === 2020) zero.add(3);
  if (year === 2026) { zero.add(10); zero.add(11); }
  return w.map((n, i) => (zero.has(i) ? 0 : n));
}

export function bucketsForYear(year: number, total: number): { key: string; paper_count: number }[] {
  const parts = distribute(total, monthWeights(year));
  return parts.map((paper_count, i) => ({ key: monthKey(year, i), paper_count }));
}

/** Sample window matches the live corpus: publication dates 2024–2026. */
export const SAMPLE_YEARS: Record<number, number> = { 2024: 4200, 2025: 8600, 2026: 7100 };

/** Extended window the corpus may grow into. Sums to 80_000. */
export const SCALE_80K_YEARS: Record<number, number> = {
  2015: 800, 2016: 1100, 2017: 1400, 2018: 1800, 2019: 2400, 2020: 3200,
  2021: 4500, 2022: 6200, 2023: 9000, 2024: 14000, 2025: 18500, 2026: 17100,
};

export function yearTotals(scale: ChartScale): Record<number, number> {
  return scale === "80k" ? SCALE_80K_YEARS : SAMPLE_YEARS;
}

export function publicationAggregate(q: { grain?: TimeGrain; year?: number | null; scale?: ChartScale }): PublicationAggregate {
  const scale = q.scale ?? "sample";
  const totals = yearTotals(scale);
  const years = Object.keys(totals).map(Number).sort((a, b) => a - b);
  if (q.grain === "month") {
    const year = q.year ?? years[years.length - 1];
    const total = totals[year] ?? 0;
    return { grain: "month", year, total, buckets: bucketsForYear(year, total) };
  }
  const buckets = years.map((year) => ({ key: String(year), paper_count: totals[year] }));
  const total = buckets.reduce((s, b) => s + b.paper_count, 0);
  return { grain: "year", year: null, total, buckets };
}

const TOPIC_NAMES = [
  "Large language models",
  "Graph neural networks",
  "Federated learning",
  "Climate modelling",
  "Protein folding",
  "Quantum computing",
  "Other",
];
/** Shares of each year's papers. They sum to 100 and shift a little so the stream moves. */
const TOPIC_WEIGHTS = [
  [28, 16, 12, 10, 9, 8, 17],
  [26, 15, 13, 11, 10, 9, 16],
  [24, 14, 14, 12, 11, 10, 15],
  [22, 13, 14, 13, 12, 11, 15],
  [30, 12, 11, 12, 10, 9, 16],
  [32, 11, 10, 11, 9, 8, 19],
];

export function topicAggregate(q: { grain?: TimeGrain; year?: number | null; scale?: ChartScale; top?: number }): TopicAggregate {
  const scale = q.scale ?? "sample";
  const totals = yearTotals(scale);
  const years = Object.keys(totals).map(Number).sort((a, b) => a - b);
  const grain = q.grain ?? "year";
  const byYear = years.map((year, yi) => {
    const weights = TOPIC_WEIGHTS[yi % TOPIC_WEIGHTS.length];
    const parts = distribute(totals[year], weights);
    return { year, parts };
  });
  if (grain === "month") {
    const year = q.year ?? years[years.length - 1];
    const row = byYear.find((r) => r.year === year);
    const parts = row?.parts ?? TOPIC_NAMES.map(() => 0);
    const series = TOPIC_NAMES.map((name, ti) => ({
      name,
      points: bucketsForYear(year, parts[ti] ?? 0).map((b) => ({ key: b.key, value: b.paper_count })),
    }));
    return { grain, year, top: q.top ?? 6, series };
  }
  const series = TOPIC_NAMES.map((name, ti) => ({
    name,
    points: byYear.map((r) => ({ key: String(r.year), value: r.parts[ti] ?? 0 })),
  }));
  return { grain: "year", year: null, top: q.top ?? 6, series };
}

const TOP_80K: [string, string, number][] = [
  ["CN", "China", 15200],
  ["US", "United States", 14100],
  ["IN", "India", 6200],
  ["GB", "United Kingdom", 4800],
  ["DE", "Germany", 4500],
  ["JP", "Japan", 3100],
  ["KR", "South Korea", 2800],
  ["FR", "France", 2600],
  ["CA", "Canada", 2400],
  ["IT", "Italy", 1900],
  ["AU", "Australia", 1700],
  ["BR", "Brazil", 1600],
];

const TAIL_80K: [string, string][] = [
  ["ES", "Spain"], ["NL", "Netherlands"], ["SE", "Sweden"], ["CH", "Switzerland"],
  ["RU", "Russia"], ["TR", "Turkey"], ["PL", "Poland"], ["BE", "Belgium"],
  ["AT", "Austria"], ["DK", "Denmark"], ["IL", "Israel"], ["SG", "Singapore"],
  ["NO", "Norway"], ["FI", "Finland"], ["PT", "Portugal"], ["IE", "Ireland"],
  ["MX", "Mexico"], ["ZA", "South Africa"], ["SA", "Saudi Arabia"], ["IR", "Iran"],
  ["EG", "Egypt"], ["ID", "Indonesia"], ["PK", "Pakistan"], ["NG", "Nigeria"],
  ["AR", "Argentina"], ["CL", "Chile"], ["CO", "Colombia"], ["MY", "Malaysia"],
  ["TH", "Thailand"], ["VN", "Vietnam"], ["NZ", "New Zealand"], ["UA", "Ukraine"],
  ["CZ", "Czechia"], ["GR", "Greece"], ["RO", "Romania"], ["HU", "Hungary"],
];

function rows80k(): [string, string, number][] {
  const named = TOP_80K.reduce((s, r) => s + r[2], 0);
  const weights = TAIL_80K.map((_, i) => TAIL_80K.length - i);
  const counts = distribute(80_000 - named, weights);
  return [...TOP_80K, ...TAIL_80K.map(([code, name], i) => [code, name, counts[i]] as [string, string, number])];
}

/** Precomputed per-country totals at the 80k corpus. Fractional papers sum to 80_000. */
export function countriesAtScale(counting: Counting): CountryStats[] {
  const years = Object.keys(SCALE_80K_YEARS).map(Number).sort((a, b) => a - b);
  const yearWeights = years.map((y) => SCALE_80K_YEARS[y]);
  return rows80k().map(([code, name, papers], i) => {
    const full = Math.round(papers * 1.18);
    const fracParts = distribute(papers, yearWeights);
    const fullParts = distribute(full, yearWeights);
    const shown = counting === "full" ? full : papers;
    return {
      code,
      name,
      papers: shown,
      growth_pct: ((i * 3) % 17) - 4,
      top_topics: ["Large language models", "Graph neural networks"].slice(0, 2),
      counting: counting === "full" ? "full" : "fractional",
      paper_count: full,
      fractional_count: papers,
      by_year: years.map((year, yi) => ({
        year,
        paper_count: fullParts[yi],
        fractional_count: fracParts[yi],
      })),
    };
  });
}
