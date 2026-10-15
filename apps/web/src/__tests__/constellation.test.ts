import { heroNetwork, nodeAmber } from "@/features/galaxy/stars";
import { clusterColors } from "@/lib/palette";

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

it("seats a multi-hub network with clear gaps", () => {
  const net = heroNetwork(papers(52));
  expect(net.nodes).toHaveLength(52);
  expect(net.nodes.filter((n) => n.role === "secondary")).toHaveLength(4);
  expect(net.nodes.some((n) => n.gap)).toBe(true);
  let min = Infinity;
  let maxR = 0;
  for (let i = 0; i < net.nodes.length; i++) {
    maxR = Math.max(maxR, Math.hypot(net.nodes[i].pos[0], net.nodes[i].pos[2]));
    for (let j = i + 1; j < net.nodes.length; j++) {
      const dx = net.nodes[i].pos[0] - net.nodes[j].pos[0];
      const dz = net.nodes[i].pos[2] - net.nodes[j].pos[2];
      min = Math.min(min, Math.hypot(dx, dz));
    }
  }
  expect(min).toBeGreaterThan(0.72);
  expect(maxR).toBeLessThan(8.6);
  expect(net.nodes.every((n) => Math.hypot(n.pos[0], n.pos[2]) > 1.3)).toBe(true);
  const clusterOf = new Map(net.nodes.map((n) => [n.id, n.clusterId]));
  const near = net.edges.filter((e) => e.kind === "near");
  const spokes = net.edges.filter((e) => e.kind === "spoke");
  const hubs = net.edges.filter((e) => e.kind === "hub");
  const pairs = new Map<string, number>();
  for (const edge of net.edges) {
    if (edge.kind === "near" || edge.kind === "spoke") {
      expect(clusterOf.get(edge.source)).toBe(clusterOf.get(edge.target));
    }
    if (edge.kind !== "cross") continue;
    const key = [clusterOf.get(edge.source), clusterOf.get(edge.target)].sort().join("|");
    pairs.set(key, (pairs.get(key) ?? 0) + 1);
  }
  expect(pairs.size).toBe(6);
  for (const count of pairs.values()) {
    expect(count).toBeGreaterThanOrEqual(6);
    expect(count).toBeLessThanOrEqual(10);
  }
  expect(near.length).toBeGreaterThan(20);
  expect(spokes.length).toBeGreaterThan(20);
  expect(hubs.length).toBeGreaterThanOrEqual(8);
  expect(heroNetwork(papers(70)).nodes).toHaveLength(56);
  expect(heroNetwork(papers(2)).nodes).toHaveLength(2);
  const shades = new Set(papers(12).map((n) => nodeAmber(0, n.clusterId, n.id)));
  expect(shades.size).toBeGreaterThan(1);
  expect([...shades].every((hex) => (clusterColors as readonly string[]).includes(hex))).toBe(true);
});
