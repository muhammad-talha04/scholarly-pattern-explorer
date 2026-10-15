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

it("resting node brightness stays in the crisp range", () => {
  expect(ink).toBe("#0B0F1A");
  expect(accent).toBe("#F5A54A");
  for (const hex of clusterColors) {
    const r = Number.parseInt(hex.slice(1, 3), 16);
    const b = Number.parseInt(hex.slice(5, 7), 16);
    expect(r).toBeGreaterThan(b + 40);
  }
  expect(NODE_BRIGHTNESS).toBeGreaterThanOrEqual(0.85);
  expect(NODE_BRIGHTNESS).toBeLessThanOrEqual(0.9);
  const scaled = scaleHex(accent, NODE_BRIGHTNESS);
  expect(scaled).not.toBe(accent);
  expect(Number.parseInt(scaled.slice(1, 3), 16)).toBeLessThan(0xf5);
});

it("twinkles only papers that arrive after the first snapshot", () => {
  sessionStorage.clear();
  expect(freshPaperIds(["a", "b"])).toEqual([]);
  expect(freshPaperIds(["a", "b", "c"])).toEqual(["c"]);
  expect(freshPaperIds(["a", "b", "c"])).toEqual(["c"]);
});
