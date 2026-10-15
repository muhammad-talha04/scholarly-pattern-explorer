import type { TopicLink } from "@/lib/graph";
import { clusterColors, galaxyColor } from "@/lib/palette";

/** One paper placed in the galaxy, with the cluster fields the shaders read. */
export interface Star {
  id: string;
  support: number;
  gap: boolean;
  gapScore?: number;
  cluster?: string;
  clusterId: string;
  colorIndex?: number;
  emerging: number;
  pos: [number, number, number];
  center: [number, number, number];
}

const SEEN_KEY = "spe-galaxy-seen";
let freshKey = "";
let freshMemo: string[] = [];

/** Papers that were not in the previous snapshot. The first visit twinkles nothing. */
export function freshPaperIds(ids: string[]): string[] {
  if (typeof sessionStorage === "undefined") return [];
  const key = ids.join("\0");
  if (key === freshKey) return freshMemo;
  let prev: string[] = [];
  try {
    const raw = JSON.parse(sessionStorage.getItem(SEEN_KEY) || "[]");
    if (Array.isArray(raw)) prev = raw.filter((id) => typeof id === "string");
  } catch { /* ignore a broken snapshot */ }
  const seen = new Set(prev);
  const fresh = prev.length ? ids.filter((id) => !seen.has(id)) : [];
  sessionStorage.setItem(SEEN_KEY, JSON.stringify(ids));
  freshKey = key;
  freshMemo = fresh;
  return fresh;
}

export function neighborIds(id: string, links: TopicLink[]) {
  const out = new Set<string>();
  for (const link of links) {
    if (link.source === id) out.add(link.target);
    else if (link.target === id) out.add(link.source);
  }
  return out;
}

export function centroid(nodes: { pos: [number, number, number] }[]): [number, number, number] {
  if (!nodes.length) return [0, 0, 0];
  const s = nodes.reduce((a, n) => [a[0] + n.pos[0], a[1] + n.pos[1], a[2] + n.pos[2]] as [number, number, number], [0, 0, 0]);
  return [s[0] / nodes.length, s[1] / nodes.length, s[2] / nodes.length];
}

/** Above this, the hero keeps a round-robin sample so the web stays readable. */
const NETWORK_CAP = 70;
/** Nodes stay inside this disc so the web fits the right-hand pane. */
const FIELD = 8.15;

type Vec = [number, number, number];
type Placed = { id: string; support: number; clusterId?: string; gap?: boolean; pos?: Vec };

export type NetRole = "node" | "secondary";
export interface NetEdge {
  source: string;
  target: string;
  a: Vec;
  b: Vec;
  /** `near` is a link inside a cluster. `hub` is a bridge, and the line shader pulses it. */
  kind: "near" | "hub";
}

/** Amber shade for one paper. Stays on the cluster ramp, with a small per-paper shift. */
export function nodeAmber(colorIndex: number | null | undefined, clusterId: string, id: string) {
  const base = galaxyColor(colorIndex, clusterId);
  const at = clusterColors.indexOf(base as (typeof clusterColors)[number]);
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h + id.charCodeAt(i)) % 997;
  return clusterColors[((at < 0 ? 0 : at) + (h % 3)) % clusterColors.length];
}

type Drawn<T> = T & { pos: Vec; center: Vec; role: NetRole; group: string };

interface Group<T> {
  id: string;
  center: Vec;
  members: Drawn<T>[];
}

/**
 * Hero drawing. Papers sit in small irregular clusters with sparse local links
 * and a few straight bridges. The same seed lays the web out the same way on every load.
 */
export function heroNetwork<T extends Placed>(nodes: T[]): {
  nodes: Drawn<T>[]; edges: NetEdge[]; hub: Vec;
} {
  const picked = nodes.length > NETWORK_CAP ? pickNetwork(nodes) : nodes.slice();
  if (!picked.length) return { nodes: [], edges: [], hub: [0, 0, 0] };
  return layClusters(picked);
}

function pickNetwork<T extends Placed>(nodes: T[]): T[] {
  const groups = new Map<string, T[]>();
  for (const n of nodes) {
    const list = groups.get(n.clusterId || "") ?? [];
    list.push(n);
    groups.set(n.clusterId || "", list);
  }
  for (const list of groups.values()) list.sort((a, b) => b.support - a.support || a.id.localeCompare(b.id));
  const picked: T[] = [];
  const seen = new Set<string>();
  const take = (n: T) => {
    if (picked.length >= NETWORK_CAP || seen.has(n.id)) return;
    seen.add(n.id);
    picked.push(n);
  };
  const gap = nodes.filter((n) => n.gap).sort((a, b) => b.support - a.support || a.id.localeCompare(b.id))[0];
  if (gap) take(gap);
  const keys = [...groups.keys()];
  let round = 0;
  while (picked.length < NETWORK_CAP) {
    let added = false;
    for (const key of keys) {
      const list = groups.get(key)!;
      if (round < list.length) {
        take(list[round]);
        added = true;
        if (picked.length >= NETWORK_CAP) break;
      }
    }
    if (!added) break;
    round++;
  }
  return picked;
}

function layClusters<T extends Placed>(nodes: T[]): { nodes: Drawn<T>[]; edges: NetEdge[]; hub: Vec } {
  const rand = mulberry(0x5eed ^ Math.imul(nodes.length, 0x9e3779b1));
  const count = clusterCount(nodes.length);
  const sizes = clusterSizes(nodes.length, count, rand);
  const centers = placeCenters(count, rand);
  const drawn: Drawn<T>[] = [];
  const groups: Group<T>[] = [];
  let cursor = 0;
  for (let g = 0; g < count; g++) {
    const slice = nodes.slice(cursor, cursor + sizes[g]);
    cursor += sizes[g];
    const spots = scatter(centers[g], slice.length, rand);
    const hubAt = slice.reduce((best, node, i) => {
      const lead = slice[best];
      if (node.support > lead.support) return i;
      if (node.support === lead.support && node.id.localeCompare(lead.id) < 0) return i;
      return best;
    }, 0);
    let nearest = 0;
    let nearestD = Infinity;
    spots.forEach((spot, i) => {
      const d = dist2(spot, centers[g]);
      if (d < nearestD) { nearestD = d; nearest = i; }
    });
    if (nearest !== hubAt) {
      const swap = spots[hubAt];
      spots[hubAt] = spots[nearest];
      spots[nearest] = swap;
    }
    const id = `c${g}`;
    const members = slice.map((node, i) => ({
      ...node,
      pos: spots[i],
      center: spots[i],
      role: (i === hubAt ? "secondary" : "node") as NetRole,
      group: id,
    }));
    drawn.push(...members);
    groups.push({ id, center: centroid(members), members });
  }
  separate(drawn, 0.74);
  clampField(drawn);
  for (const group of groups) group.center = centroid(group.members);

  const edges: NetEdge[] = [];
  const used = new Set<string>();
  for (const group of groups) {
    for (const [a, b] of linkCluster(group.members, rand)) {
      const left = group.members.find((m) => m.id === a)!;
      const right = group.members.find((m) => m.id === b)!;
      used.add(pairKey(a, b));
      edges.push({ source: a, target: b, a: left.pos, b: right.pos, kind: "near" });
    }
  }
  addBridges(groups, rand, edges, used);
  return { nodes: drawn, edges, hub: centroid(drawn) };
}

/** Seven to nine groups when the paper count can fill them. Smaller graphs use fewer. */
function clusterCount(n: number) {
  if (n <= 12) return 1;
  const lo = Math.max(1, Math.ceil(n / 12));
  const hi = Math.floor(n / 5);
  if (hi < lo) return lo;
  if (lo <= 8 && 8 <= hi) return 8;
  let best = lo;
  for (let k = lo; k <= hi; k++) if (Math.abs(k - 8) < Math.abs(best - 8)) best = k;
  return best;
}

function clusterSizes(n: number, k: number, rand: () => number) {
  if (k <= 1) return [n];
  const sizes = Array.from({ length: k }, () => 5);
  let extra = n - 5 * k;
  let guard = 0;
  while (extra > 0 && guard++ < n * 8) {
    const i = Math.floor(rand() * k);
    if (sizes[i] < 12) { sizes[i]++; extra--; }
  }
  return sizes;
}

function placeCenters(k: number, rand: () => number): Vec[] {
  if (k <= 1) return [[(rand() - 0.5) * 0.3, 0, (rand() - 0.5) * 0.3]];
  const field = 6.15;
  let minSep = 3.55;
  const centers: Vec[] = [];
  let spins = 0;
  while (centers.length < k && spins < 48) {
    spins++;
    let hit: Vec | null = null;
    let best = -1;
    let bestPos: Vec | null = null;
    for (let t = 0; t < 56; t++) {
      const ang = rand() * Math.PI * 2;
      const rad = field * Math.sqrt(0.12 + 0.88 * rand());
      const pos: Vec = [Math.cos(ang) * rad, (rand() - 0.5) * 0.35, Math.sin(ang) * rad];
      const d = centers.length ? Math.min(...centers.map((c) => dist2(c, pos))) : 99;
      if (d >= minSep) { hit = pos; break; }
      if (d > best) { best = d; bestPos = pos; }
    }
    if (hit) centers.push(hit);
    else if (bestPos && minSep < 2.55) centers.push(bestPos);
    else minSep *= 0.9;
  }
  while (centers.length < k) {
    const ang = (centers.length / k) * Math.PI * 2;
    centers.push([Math.cos(ang) * field * 0.7, 0, Math.sin(ang) * field * 0.7]);
  }
  return centers;
}

function scatter(center: Vec, count: number, rand: () => number): Vec[] {
  const reach = 0.36 + 0.25 * Math.sqrt(count);
  const pts: Vec[] = [];
  for (let i = 0; i < count; i++) {
    const ang = rand() * Math.PI * 2;
    const rad = reach * Math.sqrt(rand());
    pts.push([
      center[0] + Math.cos(ang) * rad,
      center[1] + (rand() - 0.5) * 0.18,
      center[2] + Math.sin(ang) * rad,
    ]);
  }
  const limit = reach * 1.22;
  for (let iter = 0; iter < 28; iter++) {
    for (let i = 0; i < pts.length; i++) {
      for (let j = i + 1; j < pts.length; j++) {
        let dx = pts[j][0] - pts[i][0];
        let dz = pts[j][2] - pts[i][2];
        const d = Math.hypot(dx, dz) || 0.001;
        if (d < 0.76) {
          const push = (0.76 - d) / 2;
          dx /= d; dz /= d;
          pts[i][0] -= dx * push; pts[i][2] -= dz * push;
          pts[j][0] += dx * push; pts[j][2] += dz * push;
        }
      }
      const dx = pts[i][0] - center[0];
      const dz = pts[i][2] - center[2];
      const d = Math.hypot(dx, dz);
      if (d > limit) {
        pts[i][0] = center[0] + (dx / d) * limit;
        pts[i][2] = center[2] + (dz / d) * limit;
      }
    }
  }
  return pts;
}

/** Push any two papers that landed on top of each other just far enough to read as separate spheres. */
function separate(nodes: { pos: Vec }[], min: number) {
  for (let iter = 0; iter < 16; iter++) {
    let moved = false;
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        let dx = nodes[j].pos[0] - nodes[i].pos[0];
        let dz = nodes[j].pos[2] - nodes[i].pos[2];
        const d = Math.hypot(dx, dz) || 0.001;
        if (d >= min) continue;
        const push = (min - d) / 2;
        dx /= d; dz /= d;
        nodes[i].pos[0] -= dx * push; nodes[i].pos[2] -= dz * push;
        nodes[j].pos[0] += dx * push; nodes[j].pos[2] += dz * push;
        moved = true;
      }
    }
    if (!moved) break;
  }
}

function clampField(nodes: { pos: Vec; center: Vec }[]) {
  for (const node of nodes) {
    const d = Math.hypot(node.pos[0], node.pos[2]) || 0.001;
    if (d <= FIELD) continue;
    const s = FIELD / d;
    node.pos = [node.pos[0] * s, node.pos[1], node.pos[2] * s];
    node.center = node.pos;
  }
}

function linkCluster<T extends Placed>(members: Drawn<T>[], rand: () => number): [string, string][] {
  if (members.length < 2) return [];
  const hub = members.find((m) => m.role === "secondary") ?? members[0];
  const leafCap = Math.min(members.length - 1, 3);
  const hubCap = Math.min(members.length - 1, 5);
  const hubWant = members.length <= 4 ? members.length - 1 : 4 + (rand() < 0.5 ? 1 : 0);
  const leafWant = new Map(members.filter((m) => m.id !== hub.id).map((m) => [
    m.id,
    members.length <= 3 ? 1 : 1 + Math.floor(rand() * 3),
  ]));
  const deg = new Map(members.map((m) => [m.id, 0]));
  const used = new Set<string>();
  const edges: [string, string][] = [];
  const room = (m: Drawn<T>) => (deg.get(m.id) ?? 0) < (m.id === hub.id ? hubCap : leafCap);
  const add = (a: Drawn<T>, b: Drawn<T>) => {
    const key = pairKey(a.id, b.id);
    if (a.id === b.id || used.has(key) || !room(a) || !room(b)) return false;
    used.add(key);
    edges.push([a.id, b.id]);
    deg.set(a.id, (deg.get(a.id) ?? 0) + 1);
    deg.set(b.id, (deg.get(b.id) ?? 0) + 1);
    return true;
  };
  const others = members.filter((m) => m.id !== hub.id);
  for (let i = others.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [others[i], others[j]] = [others[j], others[i]];
  }
  for (const other of others) {
    if ((deg.get(hub.id) ?? 0) >= hubWant) break;
    add(hub, other);
  }
  const open = () => members.filter((m) => (deg.get(m.id) ?? 0) === 0);
  for (const member of open()) {
    const pool = members.filter((m) => m.id !== member.id && room(m) && !used.has(pairKey(member.id, m.id)));
    if (pool.length) add(member, pool[Math.floor(rand() * pool.length)]);
  }
  const leaves = others.filter((m) => (deg.get(m.id) ?? 0) < (leafWant.get(m.id) ?? 1));
  for (const leaf of leaves) {
    const want = leafWant.get(leaf.id) ?? 1;
    let guard = 0;
    while ((deg.get(leaf.id) ?? 0) < want && guard++ < members.length) {
      const pool = others.filter((m) => m.id !== leaf.id && room(m) && !used.has(pairKey(leaf.id, m.id)));
      if (!pool.length || !add(leaf, pool[Math.floor(rand() * pool.length)])) break;
    }
  }
  return edges;
}

function addBridges<T extends Placed>(groups: Group<T>[], rand: () => number, edges: NetEdge[], used: Set<string>) {
  if (groups.length < 2) return;
  const neigh = new Set<string>();
  const neighPairs: [number, number][] = [];
  for (let i = 0; i < groups.length; i++) {
    const near = groups
      .map((group, j) => ({ j, d: dist2(groups[i].center, group.center) }))
      .filter((item) => item.j !== i)
      .sort((a, b) => a.d - b.d)
      .slice(0, Math.min(2, groups.length - 1));
    for (const item of near) {
      const a = Math.min(i, item.j);
      const b = Math.max(i, item.j);
      const key = `${a}:${b}`;
      if (neigh.has(key)) continue;
      neigh.add(key);
      neighPairs.push([a, b]);
    }
  }
  for (const [a, b] of neighPairs) join(groups[a], groups[b], 1 + Math.floor(rand() * 3), rand, edges, used);
  if (groups.length < 4) return;
  const far: { a: number; b: number; d: number }[] = [];
  for (let i = 0; i < groups.length; i++) {
    for (let j = i + 1; j < groups.length; j++) {
      if (neigh.has(`${i}:${j}`)) continue;
      far.push({ a: i, b: j, d: dist2(groups[i].center, groups[j].center) });
    }
  }
  far.sort((a, b) => b.d - a.d);
  const pool = far.slice(0, Math.max(3, Math.ceil(far.length / 3)));
  for (let i = pool.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [pool[i], pool[j]] = [pool[j], pool[i]];
  }
  for (let s = 0; s < Math.min(3, pool.length); s++) join(groups[pool[s].a], groups[pool[s].b], 1, rand, edges, used);
}

function join<T extends Placed>(a: Group<T>, b: Group<T>, count: number, rand: () => number, edges: NetEdge[], used: Set<string>) {
  let made = 0;
  let tries = 0;
  while (made < count && tries < 28) {
    tries++;
    const left = a.members[Math.floor(rand() * a.members.length)];
    const right = b.members[Math.floor(rand() * b.members.length)];
    const key = pairKey(left.id, right.id);
    if (used.has(key)) continue;
    used.add(key);
    edges.push({ source: left.id, target: right.id, a: left.pos, b: right.pos, kind: "hub" });
    made++;
  }
}

function pairKey(a: string, b: string) {
  return a < b ? `${a}|${b}` : `${b}|${a}`;
}

function mulberry(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

function dist2(a: Vec, b: Vec) {
  return Math.hypot(a[0] - b[0], a[2] - b[2]);
}

export function networkLinks(edges: NetEdge[]): TopicLink[] {
  return edges
    .filter((e) => e.source !== "hub" && e.target !== "hub")
    .map((e) => ({ source: e.source, target: e.target, weight: e.kind === "hub" ? 0.8 : 0.45 }));
}
