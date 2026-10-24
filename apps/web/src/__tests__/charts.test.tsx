import { fireEvent, render, screen } from "@testing-library/react";
import { compactCount, monthKeys, ticksOverlap, tickLabel, visibleTickIndexes } from "@/lib/charts/axis";
import { countryChartFromStats, fillMonthBuckets, parseCountryChart, parsePublication, parseTopicAggregate, percentShares, seriesFromTopicAggregate } from "@/lib/charts/aggregate";
import { countriesAtScale, publicationAggregate, topicAggregate } from "@/lib/charts/scale";
import { countries } from "@/lib/api/mock";
import { VolumeChart } from "@/features/timeline/VolumeChart";
import { CountryChart } from "@/features/countries/CountryChart";

const years = ["2015", "2016", "2017", "2018", "2019", "2020", "2021", "2022", "2023", "2024", "2025", "2026"];

it("keeps the first and last axis labels and never lets the ones it draws overlap", () => {
  const labels = years;
  const xs = labels.map((_, i) => 40 + (i / (labels.length - 1)) * 680);
  const shown = visibleTickIndexes(labels, xs);
  expect(shown[0]).toBe(0);
  expect(shown[shown.length - 1]).toBe(labels.length - 1);
  expect(ticksOverlap(labels, xs, shown)).toBe(false);

  const crowded = monthKeys(2025).flatMap((m) => years.map((y) => `${y}-${m.slice(5)}`)).slice(0, 144);
  const cxs = crowded.map((_, i) => 20 + (i / (crowded.length - 1)) * 300);
  const kept = visibleTickIndexes(crowded.map(tickLabel), cxs);
  expect(kept.length).toBeLessThan(crowded.length / 2);
  expect(ticksOverlap(crowded.map(tickLabel), cxs, kept)).toBe(false);
  expect(kept[0]).toBe(0);
});

it("fills every month, including ones the payload omitted, with zero", () => {
  const filled = fillMonthBuckets(2025, [
    { key: "2025-01", sampled: 10, estimated_total: 40 },
    { key: "2025-03", sampled: 4, estimated_total: 12 },
  ]);
  expect(filled.map((b) => b.key)).toEqual(monthKeys(2025));
  expect(filled[1]).toEqual({ key: "2025-02", sampled: 0, estimated_total: null });
  expect(filled[0].sampled).toBe(10);
  expect(filled[0].estimated_total).toBe(40);
  const parsed = parsePublication({
    grain: "month",
    year: 2024,
    sampled: 3,
    estimated_total: 9,
    buckets: [{ key: "2024-11", sampled: 3, estimated_total: 9 }],
  });
  expect(parsed?.buckets).toHaveLength(12);
  expect(parsed?.buckets.filter((b) => b.sampled === 0 && b.estimated_total == null)).toHaveLength(11);
  expect(parsed?.sampled).toBe(3);
  expect(parsed?.estimated_total).toBe(9);
});

it("keeps a null OpenAlex total from the live publication payload", () => {
  const year = parsePublication({
    grain: "year",
    year: null,
    total: 5,
    buckets: [
      { key: "2023", paper_count: 1, sampled: 1, estimated_total: null },
      { key: "2024", paper_count: 1, sampled: 1, estimated_total: null },
      { key: "2025", paper_count: 3, sampled: 3, estimated_total: 1500 },
    ],
  });
  expect(year?.sampled).toBe(5);
  expect(year?.estimated_total).toBeNull();
  expect(year?.buckets.map((b) => b.estimated_total)).toEqual([null, null, 1500]);

  const month = parsePublication({
    grain: "month",
    year: 2025,
    total: 3,
    buckets: [
      { key: "2025-01", paper_count: 2, sampled: 2, estimated_total: 1000 },
      { key: "2025-02", paper_count: 0, sampled: 0, estimated_total: null },
      { key: "2025-03", paper_count: 1, sampled: 1, estimated_total: 500 },
    ],
  });
  expect(month?.buckets).toHaveLength(12);
  expect(month?.buckets[1]).toEqual({ key: "2025-02", sampled: 0, estimated_total: null });
  expect(month?.sampled).toBe(3);
  expect(month?.estimated_total).toBe(1500);
  const { unmount } = render(<VolumeChart data={year!} />);
  expect(screen.getAllByTestId("unknown-estimate").length).toBe(2);
  expect(screen.getAllByText("unknown").length).toBeGreaterThan(0);
  unmount();
});

it("splits shares to a tenth of a percent that sums to 100", () => {
  const even = percentShares([1, 1, 1]);
  expect(even.reduce((s, n) => s + Math.round(n * 10), 0)).toBe(1000);
  expect(even[0]).toBe(33.4);
  expect(percentShares([70, 20, 10])).toEqual([70, 20, 10]);
  expect(percentShares([0, 0])).toEqual([0, 0]);
});

it("builds an 80k publication aggregate with an even sample and an uneven estimate", () => {
  const pub = publicationAggregate({ scale: "80k" });
  expect(pub.grain).toBe("year");
  expect(pub.sampled).toBe(80_000);
  expect(pub.buckets.reduce((s, b) => s + b.sampled, 0)).toBe(80_000);
  expect(pub.buckets.map((b) => b.key)).toEqual(years);
  expect(pub.buckets.length).toBeLessThan(20);
  expect(pub.buckets[pub.buckets.length - 1].estimated_total ?? 0).toBeGreaterThan((pub.buckets[0].estimated_total ?? 0) * 2);

  const active = years.flatMap((year) => publicationAggregate({ grain: "month", year: Number(year), scale: "80k" }).buckets)
    .filter((b) => b.sampled > 0);
  const sampled = active.map((b) => b.sampled);
  expect(Math.max(...sampled) - Math.min(...sampled)).toBeLessThanOrEqual(1);
  expect(sampled.reduce((s, n) => s + n, 0)).toBe(80_000);

  const early = publicationAggregate({ grain: "month", year: 2015, scale: "80k" });
  expect(early.buckets).toHaveLength(12);
  expect(early.buckets.slice(0, 9).every((b) => b.sampled === 0 && b.estimated_total === 0)).toBe(true);
  expect(early.buckets.reduce((s, b) => s + b.sampled, 0)).toBe(early.sampled);
  expect(early.sampled).toBeGreaterThan(0);

  const full2024 = publicationAggregate({ grain: "month", year: 2024, scale: "80k" });
  expect(full2024.buckets[0].sampled).toBeGreaterThan(0);
  const sample2024 = publicationAggregate({ grain: "month", year: 2024, scale: "sample" });
  expect(sample2024.buckets.slice(0, 9).every((b) => b.sampled === 0 && b.estimated_total === 0)).toBe(true);
  expect(publicationAggregate({ scale: "sample" }).sampled).toBe(19_900);

  const season = publicationAggregate({ grain: "month", year: 2025, scale: "80k" });
  const seasonActive = season.buckets.filter((b) => b.sampled > 0);
  const estimates = seasonActive.map((b) => b.estimated_total ?? 0);
  expect(Math.max(...estimates) / Math.min(...estimates)).toBeGreaterThan(1.5);
  expect(Math.max(...seasonActive.map((b) => b.sampled)) - Math.min(...seasonActive.map((b) => b.sampled))).toBeLessThanOrEqual(1);

  const hole = publicationAggregate({ grain: "month", year: 2020, scale: "80k" });
  expect(hole.buckets[3]).toEqual({ key: "2020-04", sampled: 0, estimated_total: 0 });

  const future = publicationAggregate({ grain: "month", year: 2026, scale: "80k" });
  expect(future.buckets[10].sampled).toBe(0);
  expect(future.buckets[11].estimated_total).toBe(0);
  expect(future.buckets.slice(0, 10).some((b) => b.sampled > 0)).toBe(true);
});

it("folds the country tail into Other as a percent of the period", () => {
  const rows = countriesAtScale("fractional");
  expect(rows.reduce((s, c) => s + c.papers, 0)).toBe(80_000);
  for (const c of rows) {
    expect(c.by_year?.reduce((s, y) => s + y.fractional_count, 0)).toBe(c.fractional_count);
  }
  const chart = countryChartFromStats(rows, { top: 12, counting: "fractional" });
  expect(chart.items).toHaveLength(12);
  expect(chart.other?.countries).toBe(rows.length - 12);
  const shares = [...chart.items.map((c) => c.share), chart.other?.share ?? 0];
  expect(shares.reduce((s, n) => s + Math.round(n * 10), 0)).toBe(1000);
  expect(chart.items[0]).toMatchObject({ code: "CN", share: 19 });
  expect(chart.items.map((c) => c.code)).not.toContain("HU");

  const oneYear = countryChartFromStats(rows, { top: 12, year: 2025, counting: "fractional" });
  expect(oneYear.items).toHaveLength(12);
  expect(oneYear.other).not.toBeNull();
  const yearShares = [...oneYear.items.map((c) => c.share), oneYear.other?.share ?? 0];
  expect(yearShares.reduce((s, n) => s + Math.round(n * 10), 0)).toBe(1000);

  const small = countryChartFromStats(countries("fractional").slice(0, 3), { top: 12 });
  expect(small.other).toBeNull();
  expect(small.items).toHaveLength(3);
  expect(small.items.reduce((s, c) => s + Math.round(c.share * 10), 0)).toBe(1000);

  const derived = parseCountryChart({
    counting: "fractional",
    year: null,
    top: 1,
    items: [{ code: "US", name: "United States", papers: 70 }],
    other: { papers: 30, countries: 4 },
  });
  expect(derived?.items[0].share).toBe(70);
  expect(derived?.other).toEqual({ share: 30, countries: 4 });
  const asSent = parseCountryChart({
    counting: "fractional",
    items: [{ code: "US", name: "United States", share: 40 }],
    other: { share: 30, countries: 40 },
  });
  expect(asSent?.items[0].share).toBe(40);
  expect(asSent?.other).toEqual({ share: 30, countries: 40 });
});

it("topic shares are the percent of that period, and empty months stay at zero", () => {
  const year = topicAggregate({ scale: "80k" });
  for (const key of years) {
    const sum = year.series.reduce((s, ser) => s + (ser.points.find((p) => p.key === key)?.share ?? 0), 0);
    expect(sum).toBe(100);
  }
  const month = topicAggregate({ grain: "month", year: 2015, scale: "80k" });
  expect(month.series[0].points).toHaveLength(12);
  expect(month.series.every((s) => s.points[0].share === 0)).toBe(true);
  expect(month.series.reduce((s, ser) => s + ser.points[0].share, 0)).toBe(0);
  expect(month.series.reduce((s, ser) => s + Math.round(ser.points[9].share * 10), 0)).toBe(1000);
  const full = topicAggregate({ grain: "month", year: 2024, scale: "80k" });
  expect(full.series[0].points[0].share).toBeGreaterThan(0);
  const season = topicAggregate({ grain: "month", year: 2025, scale: "80k" });
  expect(season.series[0].points[0].share).not.toBe(season.series[0].points[1].share);
  const series = seriesFromTopicAggregate(month);
  expect(series[0].keys).toHaveLength(12);
  expect(series[0].values[0]).toBe(0);

  const live = parseTopicAggregate({
    grain: "month",
    year: 2025,
    top: 1,
    series: [
      { name: "LLM", points: [{ key: "2025-01", value: 1.5 }, { key: "2025-02", value: 0 }] },
      { name: "Other", points: [{ key: "2025-01", value: 0.5 }, { key: "2025-02", value: 0 }] },
    ],
    period: [
      { key: "2025-01", sampled: 2, estimated_total: 1000 },
      { key: "2025-02", sampled: 0, estimated_total: null },
    ],
  });
  expect(live?.series.map((s) => s.points[0].share)).toEqual([75, 25]);
  expect(live?.series.every((s) => s.points[1].share === 0)).toBe(true);

  const countries = parseCountryChart({
    counting: "fractional",
    year: null,
    top: 2,
    total: 5,
    items: [
      { code: "CN", name: "China", papers: 5 },
      { code: "US", name: "United States", papers: 3 },
    ],
    other: { papers: 1.5, countries: 2 },
    period: [{ key: "2025", sampled: 5, estimated_total: 1500 }],
  });
  expect(countries?.items.map((c) => c.share)).toEqual([52.6, 31.6]);
  expect(countries?.other).toEqual({ share: 15.8, countries: 2 });
});

it("draws empty months and drills from a year bar", () => {
  const onDrill = vi.fn();
  const data = publicationAggregate({ grain: "month", year: 2024, scale: "sample" });
  render(<VolumeChart data={data} onDrill={onDrill} />);
  const gaps = screen.getAllByTestId("empty-month");
  expect(gaps.length).toBeGreaterThanOrEqual(9);
  expect(screen.getByText(/Empty months stay on the axis/)).toBeInTheDocument();
  expect(screen.getAllByText("Jan").length).toBeGreaterThan(0);
  expect(screen.getAllByText("Dec").length).toBeGreaterThan(0);

  expect(screen.getByTestId("publication-caption").textContent).toMatch(/Estimated OpenAlex output/);
  expect(screen.getByTestId("publication-caption").textContent).toMatch(/sampled/i);

  const yearly = publicationAggregate({ scale: "80k" });
  const { unmount } = render(<VolumeChart data={yearly} onDrill={onDrill} />);
  fireEvent.click(screen.getByRole("button", { name: /2025: Estimated OpenAlex output/ }));
  expect(onDrill).toHaveBeenCalledWith(2025);
  unmount();
});

it("renders a top-12 country chart as a percent of the period", () => {
  const chart = countryChartFromStats(countriesAtScale("fractional"), { top: 12 });
  render(<CountryChart data={chart} />);
  expect(screen.getByText("Percent of this period")).toBeInTheDocument();
  expect(screen.getByTestId("country-other")).toHaveTextContent("Other");
  expect(screen.getByTestId("country-other")).toHaveTextContent(String(chart.other?.countries));
  expect(screen.getByTestId("country-other")).toHaveTextContent(`${chart.other?.share.toFixed(1)}%`);
  expect(screen.getAllByRole("listitem")).toHaveLength(13);
  expect(screen.getByText("China")).toBeInTheDocument();
  expect(screen.getByText("19.0%")).toBeInTheDocument();
  expect(screen.queryByText("Hungary")).not.toBeInTheDocument();
  expect(screen.queryByText("15,200")).not.toBeInTheDocument();
  expect(compactCount(80_000)).toBe("80k");
  expect(compactCount(15_200)).toBe("15.2k");
});
