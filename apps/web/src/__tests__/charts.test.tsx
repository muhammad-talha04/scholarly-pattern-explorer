import { fireEvent, render, screen } from "@testing-library/react";
import { compactCount, monthKeys, ticksOverlap, tickLabel, visibleTickIndexes } from "@/lib/charts/axis";
import { countryChartFromStats, fillMonthBuckets, parsePublication, seriesFromTopicAggregate } from "@/lib/charts/aggregate";
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
    { key: "2025-01", paper_count: 10 },
    { key: "2025-03", paper_count: 4 },
  ]);
  expect(filled.map((b) => b.key)).toEqual(monthKeys(2025));
  expect(filled[1]).toEqual({ key: "2025-02", paper_count: 0 });
  expect(filled[0].paper_count).toBe(10);
  const parsed = parsePublication({ grain: "month", year: 2024, total: 3, buckets: [{ key: "2024-11", paper_count: 3 }] });
  expect(parsed?.buckets).toHaveLength(12);
  expect(parsed?.buckets.filter((b) => b.paper_count === 0)).toHaveLength(11);
});

it("builds an 80k publication aggregate as year totals, not paper rows", () => {
  const pub = publicationAggregate({ scale: "80k" });
  expect(pub.grain).toBe("year");
  expect(pub.total).toBe(80_000);
  expect(pub.buckets.reduce((s, b) => s + b.paper_count, 0)).toBe(80_000);
  expect(pub.buckets.map((b) => b.key)).toEqual(years);
  expect(pub.buckets.length).toBeLessThan(20);

  const early = publicationAggregate({ grain: "month", year: 2015, scale: "80k" });
  expect(early.buckets).toHaveLength(12);
  expect(early.buckets.slice(0, 9).every((b) => b.paper_count === 0)).toBe(true);
  expect(early.buckets.reduce((s, b) => s + b.paper_count, 0)).toBe(early.total);
  expect(early.total).toBe(800);

  const hole = publicationAggregate({ grain: "month", year: 2020, scale: "80k" });
  expect(hole.buckets[3]).toEqual({ key: "2020-04", paper_count: 0 });
  expect(hole.buckets.reduce((s, b) => s + b.paper_count, 0)).toBe(3200);

  const future = publicationAggregate({ grain: "month", year: 2026, scale: "80k" });
  expect(future.buckets[10].paper_count).toBe(0);
  expect(future.buckets[11].paper_count).toBe(0);
  expect(future.buckets.slice(0, 10).some((b) => b.paper_count > 0)).toBe(true);
});

it("folds the country tail into Other and keeps the 80k total", () => {
  const rows = countriesAtScale("fractional");
  expect(rows.reduce((s, c) => s + c.papers, 0)).toBe(80_000);
  for (const c of rows) {
    expect(c.by_year?.reduce((s, y) => s + y.fractional_count, 0)).toBe(c.fractional_count);
  }
  const chart = countryChartFromStats(rows, { top: 12, counting: "fractional" });
  expect(chart.items).toHaveLength(12);
  expect(chart.other?.countries).toBe(rows.length - 12);
  expect(chart.items.reduce((s, c) => s + c.papers, 0) + (chart.other?.papers ?? 0)).toBe(80_000);
  expect(chart.items[0].code).toBe("CN");
  expect(chart.items.map((c) => c.code)).not.toContain("HU");

  const oneYear = countryChartFromStats(rows, { top: 12, year: 2025, counting: "fractional" });
  expect(oneYear.items).toHaveLength(12);
  expect(oneYear.other).not.toBeNull();
  const yearSum = rows.reduce((s, c) => s + (c.by_year?.find((y) => y.year === 2025)?.fractional_count ?? 0), 0);
  expect(oneYear.total).toBeCloseTo(yearSum, 5);

  const small = countryChartFromStats(countries("fractional").slice(0, 3), { top: 12 });
  expect(small.other).toBeNull();
  expect(small.items).toHaveLength(3);
});

it("topic month series keeps empty months and sums back to the year total", () => {
  const year = topicAggregate({ scale: "80k" });
  const month = topicAggregate({ grain: "month", year: 2024, scale: "80k" });
  expect(month.series[0].points).toHaveLength(12);
  const yearTotal = year.series.reduce((s, ser) => s + (ser.points.find((p) => p.key === "2024")?.value ?? 0), 0);
  const monthTotal = month.series.reduce((s, ser) => s + ser.points.reduce((a, p) => a + p.value, 0), 0);
  expect(monthTotal).toBe(yearTotal);
  expect(month.series.every((s) => s.points[0].value === 0)).toBe(true);
  const series = seriesFromTopicAggregate(month);
  expect(series[0].keys).toHaveLength(12);
  expect(series[0].values[0]).toBe(0);
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

  const yearly = publicationAggregate({ scale: "80k" });
  const { unmount } = render(<VolumeChart data={yearly} onDrill={onDrill} />);
  fireEvent.click(screen.getByRole("button", { name: /2025/ }));
  expect(onDrill).toHaveBeenCalledWith(2025);
  unmount();
});

it("renders a top-12 country chart with an Other bucket at 80k", () => {
  const chart = countryChartFromStats(countriesAtScale("fractional"), { top: 12 });
  render(<CountryChart data={chart} />);
  expect(screen.getByTestId("country-other")).toHaveTextContent("Other");
  expect(screen.getByTestId("country-other")).toHaveTextContent(String(chart.other?.countries));
  expect(screen.getAllByRole("listitem")).toHaveLength(13);
  expect(screen.getByText("China")).toBeInTheDocument();
  expect(screen.queryByText("Hungary")).not.toBeInTheDocument();
  expect(compactCount(80_000)).toBe("80k");
  expect(compactCount(15_200)).toBe("15.2k");
});
