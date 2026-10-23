import type { ChartScale, Counting, CountryStats, PublicationAggregate, TimeBucket, TimeGrain, TopicAggregate } from "@/lib/api/types";
import { distribute, monthKeys } from "./axis";
import { percentShares } from "./aggregate";

export type { ChartScale };

const MONTH_SHAPE = [8, 7, 9, 8, 10, 9, 8, 9, 11, 12, 10, 9];

/**
 * Months forced to zero so the axis has to keep a real gap.
 * 2024 Jan–Sep, only when `partialStart` is set: the live corpus starts mid-October 2024.
 * 2015 Jan–Sep: a sparse first year once the window reaches back.
 * 2020 April: a hole in the middle of a year.
 * 2026 Nov–Dec: not published yet (the clock in this repo is October 2026).
 * The 80k window does not zero 2024.
 */
export function monthWeights(year: number, opts?: { partialStart?: boolean }): number[] {
  const zero = new Set<number>();
  if (year === 2015) for (let m = 0; m < 9; m++) zero.add(m);
  if (opts?.partialStart && year === 2024) for (let m = 0; m < 9; m++) zero.add(m);
  if (year === 2020) zero.add(3);
  if (year === 2026) { zero.add(10); zero.add(11); }
  return MONTH_SHAPE.map((n, i) => (zero.has(i) ? 0 : n));
}

function windowYears(scale: ChartScale): number[] {
  if (scale === "80k") {
    const years: number[] = [];
    for (let year = 2015; year <= 2026; year++) years.push(year);
    return years;
  }
  return [2024, 2025, 2026];
}

/** Sampled papers in the fixture. Spread evenly across active months. */
const SAMPLED_TOTAL: Record<ChartScale, number> = { sample: 19_900, "80k": 80_000 };

interface MonthCell {
  year: number;
  month: number;
  sampled: number;
  estimated_total: number;
}

/**
 * Even monthly sample, then an OpenAlex-scaled estimate.
 * `yearRate` grows with the year. Within a year the estimate follows month seasonality,
 * so the bars are not flat even though `sampled` differs by at most 1.
 */
function monthCells(scale: ChartScale): MonthCell[] {
  const partialStart = scale !== "80k";
  const slots: { year: number; month: number; weight: number; mean: number }[] = [];
  for (const year of windowYears(scale)) {
    const weights = monthWeights(year, { partialStart });
    const active = weights.filter((w) => w > 0);
    const mean = active.reduce((s, w) => s + w, 0) / (active.length || 1);
    weights.forEach((weight, month) => slots.push({ year, month, weight, mean }));
  }
  const activeIdx = slots.map((slot, i) => (slot.weight > 0 ? i : -1)).filter((i) => i >= 0);
  const sampledParts = distribute(SAMPLED_TOTAL[scale], activeIdx.map(() => 1));
  const sampledAt = new Map<number, number>();
  activeIdx.forEach((idx, k) => sampledAt.set(idx, sampledParts[k] ?? 0));
  return slots.map((slot, i) => {
    const sampled = sampledAt.get(i) ?? 0;
    const yearRate = 5 + (slot.year - 2015) * 2.5;
    const estimated_total = slot.weight > 0 ? Math.round(sampled * yearRate * (slot.weight / slot.mean)) : 0;
    return { year: slot.year, month: slot.month, sampled, estimated_total };
  });
}

/** Sampled papers per year. Sums to 19_900 (sample) or 80_000 (80k). */
export function sampledByYear(scale: ChartScale): Record<number, number> {
  const out: Record<number, number> = {};
  for (const cell of monthCells(scale)) out[cell.year] = (out[cell.year] ?? 0) + cell.sampled;
  return out;
}

function bucketsFromCells(cells: MonthCell[], year: number): TimeBucket[] {
  return monthKeys(year).map((key, month) => {
    const cell = cells.find((c) => c.year === year && c.month === month);
    return { key, sampled: cell?.sampled ?? 0, estimated_total: cell?.estimated_total ?? 0 };
  });
}

export function publicationAggregate(q: { grain?: TimeGrain; year?: number | null; scale?: ChartScale }): PublicationAggregate {
  const scale = q.scale ?? "sample";
  const cells = monthCells(scale);
  const years = windowYears(scale);
  if (q.grain === "month") {
    const year = q.year ?? years[years.length - 1];
    const buckets = bucketsFromCells(cells, year);
    return {
      grain: "month",
      year,
      sampled: buckets.reduce((s, b) => s + b.sampled, 0),
      estimated_total: buckets.reduce((s, b) => s + b.estimated_total, 0),
      buckets,
    };
  }
  const buckets = years.map((year) => {
    const rows = cells.filter((c) => c.year === year);
    return {
      key: String(year),
      sampled: rows.reduce((s, c) => s + c.sampled, 0),
      estimated_total: rows.reduce((s, c) => s + c.estimated_total, 0),
    };
  });
  return {
    grain: "year",
    year: null,
    sampled: buckets.reduce((s, b) => s + b.sampled, 0),
    estimated_total: buckets.reduce((s, b) => s + b.estimated_total, 0),
    buckets,
  };
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

/** Month columns are percents of that month. Empty months stay all zeros. Active months are not copies of each other. */
function monthTopicShares(year: number, yearIndex: number, partialStart: boolean): number[][] {
  const base = TOPIC_WEIGHTS[yearIndex % TOPIC_WEIGHTS.length] ?? TOPIC_WEIGHTS[0];
  return monthWeights(year, { partialStart }).map((weight, month) => {
    if (weight <= 0) return base.map(() => 0);
    const perturbed = base.map((bw, ti) => bw * (10 + ((month * 3 + ti * 5) % 9)));
    return percentShares(perturbed);
  });
}

export function topicAggregate(q: { grain?: TimeGrain; year?: number | null; scale?: ChartScale; top?: number }): TopicAggregate {
  const scale = q.scale ?? "sample";
  const partialStart = scale !== "80k";
  const years = windowYears(scale);
  const grain = q.grain ?? "year";
  if (grain === "month") {
    const year = q.year ?? years[years.length - 1];
    const yi = years.indexOf(year);
    const byMonth = monthTopicShares(year, yi < 0 ? 0 : yi, partialStart);
    const series = TOPIC_NAMES.map((name, ti) => ({
      name,
      points: monthKeys(year).map((key, mi) => ({ key, share: byMonth[mi]?.[ti] ?? 0 })),
    }));
    return { grain, year, top: q.top ?? 6, series };
  }
  const series = TOPIC_NAMES.map((name, ti) => ({
    name,
    points: years.map((year, yi) => ({
      key: String(year),
      share: TOPIC_WEIGHTS[yi % TOPIC_WEIGHTS.length][ti] ?? 0,
    })),
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
  const sampled = sampledByYear("80k");
  const years = Object.keys(sampled).map(Number).sort((a, b) => a - b);
  const yearWeights = years.map((y) => sampled[y]);
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
