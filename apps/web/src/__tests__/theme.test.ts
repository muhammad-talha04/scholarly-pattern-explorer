import { accent, clusterColors, galaxyColor, ink, NODE_BRIGHTNESS, okabeIto, otherColor, scaleHex } from "@/lib/palette";
import { freshPaperIds } from "@/features/galaxy/stars";

it("maps galaxy clusters by color_index, then id, and greys the rest", () => {
  expect(galaxyColor(0, "ignored")).toBe(clusterColors[0]);
  expect(galaxyColor(4, "ignored")).toBe(clusterColors[4]);
  expect(galaxyColor(5, "extra")).toBe(otherColor);
  expect(galaxyColor(-1, "extra")).toBe(otherColor);
  const a = galaxyColor(undefined, "methods");
  const b = galaxyColor(null, "methods");
  expect(a).toBe(b);
  expect(clusterColors).toContain(a);
  expect(okabeIto).toHaveLength(7);
});

it("uses the Champagne and Platinum palette at a crisp node brightness", () => {
  expect(ink).toBe("#121216");
  expect(accent).toBe("#F3E3B5");
  expect([...clusterColors]).toEqual(["#D9C28E", "#C7CCD4", "#BFA36A", "#9EA4AE", "#E6DCC0"]);
  expect(otherColor).toBe("#6E6E76");
  expect(NODE_BRIGHTNESS).toBe(0.875);
  const scaled = scaleHex(accent, NODE_BRIGHTNESS);
  expect(scaled).not.toBe(accent);
  expect(Number.parseInt(scaled.slice(1, 3), 16)).toBeLessThan(0xf3);
});

it("twinkles only papers that arrive after the first snapshot", () => {
  sessionStorage.clear();
  expect(freshPaperIds(["a", "b"])).toEqual([]);
  expect(freshPaperIds(["a", "b", "c"])).toEqual(["c"]);
  expect(freshPaperIds(["a", "b", "c"])).toEqual(["c"]);
});
