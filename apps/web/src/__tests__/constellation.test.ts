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

function hypot(a: [number, number, number], b: [number, number, number]) {
  return Math.hypot(a[0] - b[0], a[2] - b[2]);
}

it("lays papers out as a seeded neural web of small clusters", () => {
  const net = heroNetwork(papers(66));
  expect(net.nodes).toHaveLength(66);
  expect(net.nodes.some((n) => n.gap)).toBe(true);
  expect("filaments" in net).toBe(false);

  const groups = new Map<string, typeof net.nodes>();
  for (const node of net.nodes) {
    const list = groups.get(node.group) ?? [];
    list.push(node);
    groups.set(node.group, list);
  }
  expect(groups.size).toBeGreaterThanOrEqual(7);
  expect(groups.size).toBeLessThanOrEqual(9);

  let min = Infinity;
  let maxR = 0;
  for (let i = 0; i < net.nodes.length; i++) {
    maxR = Math.max(maxR, Math.hypot(net.nodes[i].pos[0], net.nodes[i].pos[2]));
    for (let j = i + 1; j < net.nodes.length; j++) min = Math.min(min, hypot(net.nodes[i].pos, net.nodes[j].pos));
  }
  expect(min).toBeGreaterThan(0.7);
  expect(maxR).toBeLessThan(8.5);

  const centroids = [...groups.entries()].map(([id, members]) => {
    const c = members.reduce((a, n) => [a[0] + n.pos[0], a[1] + n.pos[2]], [0, 0]);
    return { id, c: [c[0] / members.length, c[1] / members.length] as [number, number] };
  });
  let gap = Infinity;
  for (let i = 0; i < centroids.length; i++) {
    for (let j = i + 1; j < centroids.length; j++) {
      gap = Math.min(gap, Math.hypot(centroids[i].c[0] - centroids[j].c[0], centroids[i].c[1] - centroids[j].c[1]));
    }
  }
  expect(gap).toBeGreaterThan(2.2);

  for (const members of groups.values()) {
    expect(members.length).toBeGreaterThanOrEqual(5);
    expect(members.length).toBeLessThanOrEqual(12);
    expect(members.filter((n) => n.role === "secondary")).toHaveLength(1);
    const ids = new Set(members.map((n) => n.id));
    const local = net.edges.filter((e) => e.kind === "near" && ids.has(e.source) && ids.has(e.target));
    const possible = (members.length * (members.length - 1)) / 2;
    expect(local.length).toBeGreaterThan(0);
    expect(local.length).toBeLessThan(possible);
    const deg = new Map(members.map((n) => [n.id, 0]));
    for (const edge of local) {
      deg.set(edge.source, (deg.get(edge.source) ?? 0) + 1);
      deg.set(edge.target, (deg.get(edge.target) ?? 0) + 1);
    }
    for (const member of members) {
      const d = deg.get(member.id) ?? 0;
      if (member.role === "secondary") {
        expect(d).toBeGreaterThanOrEqual(4);
        expect(d).toBeLessThanOrEqual(5);
      } else {
        expect(d).toBeGreaterThanOrEqual(1);
        expect(d).toBeLessThanOrEqual(3);
      }
    }
  }

  const pair = (a: string, b: string) => (a < b ? `${a}|${b}` : `${b}|${a}`);
  const groupOf = new Map(net.nodes.map((n) => [n.id, n.group]));
  const bridgeCount = new Map<string, number>();
  for (const edge of net.edges.filter((e) => e.kind === "hub")) {
    const a = groupOf.get(edge.source)!;
    const b = groupOf.get(edge.target)!;
    expect(a).not.toBe(b);
    const key = pair(a, b);
    bridgeCount.set(key, (bridgeCount.get(key) ?? 0) + 1);
  }
  const neigh = new Set<string>();
  for (const c of centroids) {
    const near = centroids
      .filter((o) => o.id !== c.id)
      .sort((a, b) => Math.hypot(a.c[0] - c.c[0], a.c[1] - c.c[1]) - Math.hypot(b.c[0] - c.c[0], b.c[1] - c.c[1]))
      .slice(0, 2);
    for (const n of near) neigh.add(pair(c.id, n.id));
  }
  for (const key of neigh) {
    const count = bridgeCount.get(key) ?? 0;
    expect(count).toBeGreaterThanOrEqual(1);
    expect(count).toBeLessThanOrEqual(3);
  }
  const centroidDist = (key: string) => {
    const [a, b] = key.split("|");
    const left = centroids.find((c) => c.id === a)!;
    const right = centroids.find((c) => c.id === b)!;
    return Math.hypot(left.c[0] - right.c[0], left.c[1] - right.c[1]);
  };
  const neighD = [...neigh].map(centroidDist).sort((a, b) => a - b);
  const skips = [...bridgeCount.keys()].filter((key) => !neigh.has(key));
  expect(skips.length).toBeGreaterThanOrEqual(1);
  const median = neighD[Math.floor(neighD.length / 2)];
  expect(Math.max(...skips.map(centroidDist))).toBeGreaterThan(median);

  const again = heroNetwork(papers(66));
  expect(again.nodes.map((n) => n.pos)).toEqual(net.nodes.map((n) => n.pos));
  expect(again.edges.map((e) => [e.source, e.target, e.kind])).toEqual(net.edges.map((e) => [e.source, e.target, e.kind]));

  expect(heroNetwork(papers(80)).nodes).toHaveLength(70);
  expect(heroNetwork(papers(2)).nodes).toHaveLength(2);
  const shades = new Set(papers(12).map((n) => nodeAmber(0, n.clusterId, n.id)));
  expect(shades.size).toBeGreaterThan(1);
  expect([...shades].every((hex) => (clusterColors as readonly string[]).includes(hex))).toBe(true);
});
