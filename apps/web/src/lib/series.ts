import type { Counting, TopicCountryYear } from "./api/types";

export interface TopicSeries { name: string; years: number[]; values: number[] }

/** Sum fractional counts by topic and year. The largest topics stay named; the rest fold into Other. */
export function topicSeries(rows: TopicCountryYear[], topN = 6, includeOther = true): TopicSeries[] {
  const years = [...new Set(rows.map((r) => r.year))].sort((a, b) => a - b);
  const totals = new Map<string, number>();
  const cell = new Map<string, number>();
  for (const r of rows) {
    totals.set(r.topic_name, (totals.get(r.topic_name) ?? 0) + r.fractional_count);
    cell.set(`${r.topic_name}|${r.year}`, (cell.get(`${r.topic_name}|${r.year}`) ?? 0) + r.fractional_count);
  }
  const ranked = [...totals.entries()].sort((a, b) => b[1] - a[1]);
  const keep = ranked.slice(0, topN).map(([name]) => name);
  const rest = ranked.slice(topN).map(([name]) => name);
  const series: TopicSeries[] = keep.map((name) => ({
    name,
    years,
    values: years.map((y) => cell.get(`${name}|${y}`) ?? 0),
  }));
  if (includeOther && rest.length) {
    series.push({
      name: "Other",
      years,
      values: years.map((y) => rest.reduce((s, name) => s + (cell.get(`${name}|${y}`) ?? 0), 0)),
    });
  }
  return series;
}

/** Centered stack: each band is [y0, y1] around zero, suitable for a streamgraph. */
export function streamBands(series: TopicSeries[]): { name: string; points: { year: number; y0: number; y1: number }[] }[] {
  if (!series.length) return [];
  const years = series[0].years;
  const baseline = years.map(() => 0);
  const raw = series.map((s) => s.values.map((v, i) => {
    const y0 = baseline[i];
    baseline[i] += v;
    return [y0, baseline[i]] as const;
  }));
  return series.map((s, si) => ({
    name: s.name,
    points: years.map((year, i) => ({
      year,
      y0: raw[si][i][0] - baseline[i] / 2,
      y1: raw[si][i][1] - baseline[i] / 2,
    })),
  }));
}

export function papersByCountryYear(rows: TopicCountryYear[], year: number, counting: Counting): Map<string, number> {
  const m = new Map<string, number>();
  for (const r of rows) {
    if (r.year !== year) continue;
    const add = counting === "full" ? r.paper_count : r.fractional_count;
    m.set(r.country_code, (m.get(r.country_code) ?? 0) + add);
  }
  return m;
}

export function yearRange(rows: TopicCountryYear[]): [number, number] | null {
  if (!rows.length) return null;
  let min = rows[0].year, max = rows[0].year;
  for (const r of rows) { if (r.year < min) min = r.year; if (r.year > max) max = r.year; }
  return [min, max];
}
