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

function bow(pts: { pos: [number, number, number] }[]) {
  const a = pts[0].pos;
  const b = pts[pts.length - 1].pos;
  const mid = pts[Math.floor(pts.length / 2)].pos;
  const dx = b[0] - a[0];
  const dz = b[2] - a[2];
  const len2 = dx * dx + dz * dz || 1;
  const t = ((mid[0] - a[0]) * dx + (mid[2] - a[2]) * dz) / len2;
  return Math.hypot(mid[0] - (a[0] + dx * t), mid[2] - (a[2] + dz * t));
}

it("grows a curved filament web with hubs, junctions, and specks", () => {
  const net = heroNetwork(papers(52));
  expect(net.nodes).toHaveLength(52);
  const hubs = net.nodes.filter((n) => n.role === "hub");
  expect(hubs.length).toBeGreaterThanOrEqual(5);
  expect(hubs.length).toBeLessThanOrEqual(7);
  expect(hubs.filter((n) => n.hubRank === 0)).toHaveLength(1);
  expect(net.nodes.some((n) => n.gap)).toBe(true);
  let min = Infinity;
  let maxR = 0;
  for (let i = 0; i < net.nodes.length; i++) {
    maxR = Math.max(maxR, Math.hypot(net.nodes[i].pos[0], net.nodes[i].pos[2]));
    for (let j = i + 1; j < net.nodes.length; j++) {
      min = Math.min(min, Math.hypot(net.nodes[i].pos[0] - net.nodes[j].pos[0], net.nodes[i].pos[2] - net.nodes[j].pos[2]));
    }
  }
  expect(min).toBeGreaterThan(0.4);
  expect(maxR).toBeLessThan(9.2);
  let hubSpan = 0;
  for (let i = 0; i < hubs.length; i++) {
    for (let j = i + 1; j < hubs.length; j++) {
      hubSpan = Math.max(hubSpan, Math.hypot(hubs[i].pos[0] - hubs[j].pos[0], hubs[i].pos[2] - hubs[j].pos[2]));
    }
  }
  expect(hubSpan).toBeGreaterThan(8);
  const bridges = net.filaments.filter((f) => f.kind === "bridge");
  const branches = net.filaments.filter((f) => f.kind === "branch");
  const longBranches = branches.filter((f) => {
    let length = 0;
    for (let i = 1; i < f.pts.length; i++) {
      length += Math.hypot(f.pts[i].pos[0] - f.pts[i - 1].pos[0], f.pts[i].pos[2] - f.pts[i - 1].pos[2]);
    }
    return length > 3;
  });
  expect(bridges.length).toBeGreaterThanOrEqual(5);
  expect(branches.length).toBeGreaterThan(40);
  expect(longBranches.length).toBeGreaterThan(12);
  expect(bridges.filter((f) => bow(f.pts) > 0.2).length).toBeGreaterThan(bridges.length / 2);
  expect(bridges.every((f) => f.pts[0].depth < 0.15 && f.pts[f.pts.length - 1].depth < 0.15)).toBe(true);
  expect(bridges.every((f) => f.pts[Math.floor(f.pts.length / 2)].depth > 0.7)).toBe(true);
  expect(net.specks.length).toBeGreaterThanOrEqual(280);
  expect(net.specks.length).toBeLessThanOrEqual(800);
  expect(net.specks.filter((s) => s.bright).length).toBeGreaterThan(20);
  expect(net.filaments.some((f) => f.pts.some((p) => p.pulse > 0))).toBe(true);
  expect(heroNetwork(papers(70)).nodes).toHaveLength(56);
  expect(heroNetwork(papers(2)).nodes).toHaveLength(2);
  const shades = new Set(papers(12).map((n) => nodeAmber(0, n.clusterId, n.id)));
  expect(shades.size).toBeGreaterThan(1);
  expect([...shades].every((hex) => (clusterColors as readonly string[]).includes(hex))).toBe(true);
});
