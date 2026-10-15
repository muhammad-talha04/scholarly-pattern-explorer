import { heroNetwork, LINK_REACH, nodeAmber, PLEXUS_COUNT, plexusCore, plexusTint } from "@/features/galaxy/stars";
import { accent, clusterColors, plexusCopper, plexusGold } from "@/lib/palette";

function papers(count: number) {
  return Array.from({ length: count }, (_, i) => ({
    id: `p${i}`,
    support: 1 - (i % 5) * 0.1,
    clusterId: ["methods", "science", "systems", "society"][i % 4],
    gap: i === 7,
    pos: [0, 0, 0] as [number, number, number],
    center: [0, 0, 0] as [number, number, number],
  }));
}

function pearson(xs: number[], ys: number[]) {
  const n = xs.length;
  const mx = xs.reduce((a, v) => a + v, 0) / n;
  const my = ys.reduce((a, v) => a + v, 0) / n;
  let num = 0;
  let dx = 0;
  let dy = 0;
  for (let i = 0; i < n; i++) {
    const a = xs[i] - mx;
    const b = ys[i] - my;
    num += a * b;
    dx += a * a;
    dy += b * b;
  }
  return num / Math.sqrt(dx * dy);
}

it("builds a seeded diagonal plexus band", () => {
  const net = heroNetwork(papers(66));
  expect(net.nodes.length).toBe(PLEXUS_COUNT);
  expect(net.nodes.length).toBeGreaterThanOrEqual(250);
  expect(net.nodes.length).toBeLessThanOrEqual(350);
  expect(net.nodes.filter((n) => n.paper)).toHaveLength(66);
  expect(net.nodes.some((n) => n.gap && n.paper)).toBe(true);
  expect("filaments" in net).toBe(false);

  const corr = pearson(net.nodes.map((n) => n.pos[0]), net.nodes.map((n) => -n.pos[2]));
  expect(corr).toBeGreaterThan(0.8);

  const mid = net.nodes.filter((n) => n.t > 0.35 && n.t < 0.65).length;
  const ends = net.nodes.filter((n) => n.t < 0.18 || n.t > 0.82).length;
  expect(mid).toBeGreaterThan(ends * 1.4);

  const deg = new Map(net.nodes.map((n) => [n.id, 0]));
  let maxSpan = 0;
  for (const edge of net.edges) {
    deg.set(edge.source, (deg.get(edge.source) ?? 0) + 1);
    deg.set(edge.target, (deg.get(edge.target) ?? 0) + 1);
    maxSpan = Math.max(maxSpan, edge.span);
    expect(edge.span).toBeLessThanOrEqual(LINK_REACH + 1e-6);
    expect(edge.alpha).toBeGreaterThan(0);
    expect(edge.alpha).toBeLessThan(0.6);
  }
  const degrees = [...deg.values()].sort((a, b) => a - b);
  expect(Math.max(...degrees)).toBeLessThanOrEqual(6);
  const median = degrees[Math.floor(degrees.length / 2)];
  expect(median).toBeGreaterThanOrEqual(3);
  expect(median).toBeLessThanOrEqual(6);
  expect(degrees.filter((d) => d === 0).length).toBeLessThan(net.nodes.length * 0.08);
  expect(maxSpan).toBeLessThan(4);

  const short = net.edges.filter((e) => e.span < maxSpan * 0.45);
  const long = net.edges.filter((e) => e.span > maxSpan * 0.8);
  if (short.length && long.length) expect(short[0].alpha).toBeGreaterThan(long[0].alpha);

  const again = heroNetwork(papers(66));
  expect(again.nodes.map((n) => [n.id, ...n.pos])).toEqual(net.nodes.map((n) => [n.id, ...n.pos]));
  expect(again.edges.map((e) => [e.source, e.target])).toEqual(net.edges.map((e) => [e.source, e.target]));

  const two = heroNetwork(papers(2));
  expect(two.nodes.filter((n) => n.paper).map((n) => n.id).sort()).toEqual(["p0", "p1"]);
  expect(heroNetwork([])).toEqual({ nodes: [], edges: [], hub: [0, 0, 0] });

  expect(plexusTint(0)).toBe(plexusCopper);
  expect(plexusTint(0.5)).toBe(accent);
  expect(plexusTint(1)).toBe(plexusGold);
  expect(plexusCore(0.5)).not.toBe(accent);

  const shades = new Set(papers(12).map((n) => nodeAmber(0, n.clusterId, n.id)));
  expect(shades.size).toBeGreaterThan(1);
  expect([...shades].every((hex) => (clusterColors as readonly string[]).includes(hex))).toBe(true);
});
