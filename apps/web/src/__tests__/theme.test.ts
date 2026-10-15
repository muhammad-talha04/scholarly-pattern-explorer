import { clusterColors, galaxyColor, NODE_BRIGHTNESS, okabeIto, otherColor, scaleHex } from "@/lib/theme";
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

it("resting node brightness stays in the crisp range", () => {
  expect(NODE_BRIGHTNESS).toBeGreaterThanOrEqual(0.85);
  expect(NODE_BRIGHTNESS).toBeLessThanOrEqual(0.9);
  const scaled = scaleHex("#D9C28E", NODE_BRIGHTNESS);
  expect(scaled).not.toBe("#D9C28E");
  expect(parseInt(scaled.slice(1, 3), 16)).toBeLessThan(0xd9);
});

it("twinkles only papers that arrive after the first snapshot", () => {
  sessionStorage.clear();
  expect(freshPaperIds(["a", "b"])).toEqual([]);
  expect(freshPaperIds(["a", "b", "c"])).toEqual(["c"]);
  expect(freshPaperIds(["a", "b", "c"])).toEqual(["c"]);
});
