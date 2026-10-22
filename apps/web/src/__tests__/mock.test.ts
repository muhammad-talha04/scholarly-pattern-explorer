import * as m from "@/lib/api/mock";
it("fixtures match schemas.py shapes", () => {
  const page = m.search({ q: "x", limit: 5, offset: 1 });
  expect(page.total).toBe(m.FIXTURE_COUNT);
  expect(page.results).toHaveLength(5);
  expect(page.offset).toBe(1);
  const p = m.paper(page.results[0].id);
  for (const k of ["id", "title", "authors", "year", "cited_by", "one_line_summary", "score", "abstract", "summary", "topics", "countries", "original_url", "openalex_url"]) expect(p).toHaveProperty(k);
  const blob = JSON.stringify(m.search({ q: "a", limit: m.FIXTURE_COUNT }).results.map((r) => m.paper(r.id)));
  expect(blob).not.toContain("10.1234");
  expect(p.original_url).toBe(`https://openalex.org/works?search=${encodeURIComponent(p.title)}`);
  expect(p.openalex_url).toBe(p.original_url);
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
  expect(g.nodes).toHaveLength(66);
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
