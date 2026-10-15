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
  const net = heroNetwork(papers(42));
  expect(net.nodes.length).toBeGreaterThanOrEqual(35);
  expect(net.nodes.length).toBeLessThanOrEqual(50);
  expect(net.nodes.filter((n) => n.role === "secondary")).toHaveLength(4);
  expect(net.nodes.some((n) => n.gap)).toBe(true);
  let min = Infinity;
  for (let i = 0; i < net.nodes.length; i++) {
    for (let j = i + 1; j < net.nodes.length; j++) {
      const dx = net.nodes[i].pos[0] - net.nodes[j].pos[0];
      const dz = net.nodes[i].pos[2] - net.nodes[j].pos[2];
      min = Math.min(min, Math.hypot(dx, dz));
    }
  }
  expect(min).toBeGreaterThan(0.72);
  expect(net.nodes.every((n) => Math.hypot(n.pos[0], n.pos[2]) > 1.3 && Math.hypot(n.pos[0], n.pos[2]) < 8)).toBe(true);
  const near = net.edges.filter((e) => e.kind === "near");
  const spokes = net.edges.filter((e) => e.kind === "spoke");
  const hubs = net.edges.filter((e) => e.kind === "hub");
  expect(near.length).toBeGreaterThan(net.nodes.length);
  expect(spokes.length).toBeGreaterThan(20);
  expect(hubs.length).toBeGreaterThanOrEqual(4);
  expect(heroNetwork(papers(60)).nodes).toHaveLength(48);
  expect(heroNetwork(papers(2)).nodes).toHaveLength(2);
  const shades = new Set(papers(12).map((n) => nodeAmber(0, n.clusterId, n.id)));
  expect(shades.size).toBeGreaterThan(1);
  expect([...shades].every((hex) => (clusterColors as readonly string[]).includes(hex))).toBe(true);
});
