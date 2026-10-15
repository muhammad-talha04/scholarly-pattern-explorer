import { patterns } from "@/lib/api/mock";
import { buildTopicGraph, lifecycles, selectBornDied } from "@/lib/graph";
import { deriveRules } from "@/features/patterns/rules";
const P = (items: string[], support: number, w = 2020) => ({ items, support, window_start: w, window_end: w + 1 });
it("builds nodes and co-occurrence links, flags gaps", () => {
  const g = buildTopicGraph([P(["A"], 0.4), P(["B"], 0.2), P(["A", "B"], 0.1)], [P(["C"], 0.9)]);
  expect(g.nodes.map((n) => n.id)).toEqual(["A", "B", "C"]);
  expect(g.links).toEqual([{ source: "A", target: "B", weight: 0.1 }]);
  expect(g.nodes.find((n) => n.id === "C")!.gap).toBe(true);
});
it("derives rules with confidence and lift", () => {
  const r = deriveRules([P(["A"], 0.4), P(["B"], 0.2), P(["A", "B"], 0.1)]);
  const ab = r.find((x) => x.antecedent[0] === "A")!;
  expect(ab.confidence).toBeCloseTo(0.25); expect(ab.lift).toBeCloseTo(1.25);
});
it("computes lifecycles born/died", () => {
  const l = lifecycles([P(["A"], 0.1, 2019), P(["A"], 0.1, 2021), P(["B"], 0.1, 2021), P(["B"], 0.1, 2023), P(["C"], 0.1, 2023)]);
  const by = Object.fromEntries(l.rows.map((r) => [r.key, r]));
  expect(by.A.died).toBe(2023); expect(by.B.born).toBe(2021); expect(by.C.died).toBeNull();
});
it("mock patterns born and died in the latest window", () => {
  const life = selectBornDied(patterns(), 2026);
  expect(life.note).toBe("matched");
  expect(life.win).toBe(2025);
  expect(life.born.length).toBeGreaterThan(0);
  expect(life.died.length).toBeGreaterThan(0);
});
