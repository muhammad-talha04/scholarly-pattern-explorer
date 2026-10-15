import { papersByCountryYear, streamBands, topicSeries, yearRange } from "@/lib/series";
import { topicCountryYears } from "@/lib/api/mock";
import { borderPositions, bordersPath, countryBorders } from "@/lib/world";

it("builds a centered topic stream from the topic-year table", () => {
  const rows = topicCountryYears();
  expect(yearRange(rows)?.[0]).toBeLessThan(yearRange(rows)![1]);
  const series = topicSeries(rows, 4);
  expect(series.length).toBe(5);
  const bands = streamBands(series);
  const year = bands[0].points.length - 1;
  const span = bands.reduce((s, b) => s + (b.points[year].y1 - b.points[year].y0), 0);
  const top = Math.max(...bands.map((b) => b.points[year].y1));
  const bot = Math.min(...bands.map((b) => b.points[year].y0));
  expect(top + bot).toBeCloseTo(0, 5);
  expect(span).toBeGreaterThan(0);
});

it("year slider uses fractional or full counts", () => {
  const rows = topicCountryYears({ year: 2024, country: "US" });
  expect(rows.length).toBeGreaterThan(0);
  const frac = papersByCountryYear(topicCountryYears(), 2024, "fractional").get("US")!;
  const full = papersByCountryYear(topicCountryYears(), 2024, "full").get("US")!;
  expect(full).toBeGreaterThan(frac);
});

it("loads natural earth country outlines", () => {
  expect(countryBorders().length).toBeGreaterThan(50);
  expect(bordersPath(800, 400).startsWith("M")).toBe(true);
  expect(borderPositions(2).length).toBeGreaterThan(1000);
});
