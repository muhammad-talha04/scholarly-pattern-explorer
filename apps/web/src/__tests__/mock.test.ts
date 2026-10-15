import * as m from "@/lib/api/mock";
it("fixtures match schemas.py shapes", () => {
  const p = m.paper(m.search({ q: "x" }).results[0].id);
  for (const k of ["id", "title", "authors", "year", "cited_by", "one_line_summary", "score", "abstract", "summary", "topics", "countries", "original_url", "openalex_url"]) expect(p).toHaveProperty(k);
  const g = m.gaps()[0];
  expect(g.items).toHaveLength(1); expect(g.gap_score).toBe(g.support);
  const r = m.runs()[0];
  expect(Object.keys(r).sort()).toEqual(["finished_at", "id", "papers_added", "patterns_changed", "started_at", "status"]);
});
it("full counting >= fractional counting", () => {
  const f = m.countries("fractional"), full = m.countries("full");
  f.forEach((c, i) => expect(full[i].papers).toBeGreaterThanOrEqual(c.papers));
});
it("galaxy fixtures are papers in topic clusters", () => {
  const g = m.galaxy();
  expect(g.clusters.map((c) => c.name).sort()).toEqual(["Methods", "Science", "Society", "Systems"]);
  expect(g.nodes).toHaveLength(52);
  const byCluster = new Map<string, number>();
  for (const n of g.nodes) byCluster.set(n.cluster_id, (byCluster.get(n.cluster_id) ?? 0) + 1);
  expect(Math.min(...byCluster.values())).toBeGreaterThanOrEqual(8);
  expect(g.nodes.every((n) => n.topic_name.includes("meets"))).toBe(true);
  expect(g.nodes.every((n) => g.clusters.some((c) => c.id === n.cluster_id))).toBe(true);
});
it("search filters by country and year", () => {
  const res = m.search({ q: "learning", country: "PK", year_from: 2020 }).results;
  res.forEach((r) => { expect(m.paper(r.id).countries).toContain("PK"); expect(r.year!).toBeGreaterThanOrEqual(2020); });
});
