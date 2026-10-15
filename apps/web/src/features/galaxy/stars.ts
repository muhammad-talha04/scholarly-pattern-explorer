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

const GOLDEN = Math.PI * (3 - Math.sqrt(5));
/** Above this, the hero keeps a round-robin sample so the disc stays readable. */
const NETWORK_CAP = 56;

type Placed = { id: string; support: number; clusterId?: string; gap?: boolean; pos?: [number, number, number] };

export type NetRole = "node" | "secondary";
export interface NetEdge {
  source: string;
  target: string;
  a: [number, number, number];
  b: [number, number, number];
  kind: "near" | "spoke" | "hub" | "cross";
}

/** Amber shade for one paper. Stays on the cluster ramp, with a small per-paper shift. */
export function nodeAmber(colorIndex: number | null | undefined, clusterId: string, id: string) {
  const base = galaxyColor(colorIndex, clusterId);
  const at = clusterColors.indexOf(base as (typeof clusterColors)[number]);
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h + id.charCodeAt(i)) % 997;
  return clusterColors[((at < 0 ? 0 : at) + (h % 3)) % clusterColors.length];
}

type Drawn<T> = T & { pos: [number, number, number]; center: [number, number, number]; role: NetRole };

/**
 * Hero drawing. Up to 56 papers, seated as a few sub-clusters around a main hub.
 * Each sub-cluster has a secondary hub. Links stay inside the cluster, and each
 * cluster pair also gets a handful of dimmer cross edges.
 */
export function heroNetwork<T extends Placed>(nodes: T[]): { nodes: Drawn<T>[]; edges: NetEdge[]; hub: [number, number, number] } {
  const hub: [number, number, number] = [0, 0, 0];
  const picked = nodes.length > NETWORK_CAP ? pickNetwork(nodes) : nodes.slice();
  const placed = placeNetwork(picked);
  return { nodes: placed, edges: buildEdges(placed, hub), hub };
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

function placeNetwork<T extends Placed>(nodes: T[]): Drawn<T>[] {
  const groups = new Map<string, T[]>();
  for (const n of nodes) {
    const list = groups.get(n.clusterId || "") ?? [];
    list.push(n);
    groups.set(n.clusterId || "", list);
  }
  for (const list of groups.values()) list.sort((a, b) => b.support - a.support || a.id.localeCompare(b.id));
  const keys = [...groups.keys()].sort();
  const g = keys.length;
  const out: Drawn<T>[] = [];
  keys.forEach((key, gi) => {
    const list = groups.get(key)!;
    const ang = g === 1 ? 0.5 : (gi / g) * Math.PI * 2 - Math.PI / 2;
    const ring = g === 1 ? 3.1 : 5.05;
    const hx = ring * Math.cos(ang);
    const hz = ring * Math.sin(ang);
    const hy = ((gi % 5) - 2) * 0.06;
    const center: [number, number, number] = [hx, hy, hz];
    const satellites = Math.max(1, list.length - 1);
    const localMax = Math.min(2.45, 0.95 + 0.32 * Math.sqrt(satellites));
    list.forEach((node, i) => {
      let pos: [number, number, number];
      if (i === 0) pos = [hx, hy, hz];
      else {
        const t = Math.sqrt((i - 1) / satellites);
        const lr = 0.82 + t * (localMax - 0.82);
        const la = i * GOLDEN;
        pos = [hx + lr * Math.cos(la), hy + (((i * 3) % 5) - 2) * 0.035, hz + lr * Math.sin(la)];
      }
      out.push({ ...node, pos, center, role: i === 0 ? "secondary" : "node" });
    });
  });
  separate(out, 0.8, 24);
  return out;
}

function separate<T extends { pos: [number, number, number] }>(nodes: T[], min: number, iters: number) {
  for (let k = 0; k < iters; k++) {
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const dx = nodes[j].pos[0] - nodes[i].pos[0];
        const dz = nodes[j].pos[2] - nodes[i].pos[2];
        const d = Math.hypot(dx, dz) || 0.0001;
        if (d >= min) continue;
        const push = (min - d) / 2;
        const ux = dx / d;
        const uz = dz / d;
        nodes[i].pos = [nodes[i].pos[0] - ux * push, nodes[i].pos[1], nodes[i].pos[2] - uz * push];
        nodes[j].pos = [nodes[j].pos[0] + ux * push, nodes[j].pos[1], nodes[j].pos[2] + uz * push];
      }
    }
    for (const n of nodes) {
      const d = Math.hypot(n.pos[0], n.pos[2]) || 0.001;
      if (d < 1.5) {
        const s = 1.5 / d;
        n.pos = [n.pos[0] * s, n.pos[1], n.pos[2] * s];
      }
    }
  }
}

function buildEdges<T extends Placed>(nodes: Drawn<T>[], hub: [number, number, number]): NetEdge[] {
  const edges: NetEdge[] = [];
  const seen = new Set<string>();
  const add = (source: string, target: string, a: [number, number, number], b: [number, number, number], kind: NetEdge["kind"]) => {
    const key = [source, target].sort().join("|");
    if (seen.has(key) || source === target) return false;
    seen.add(key);
    edges.push({ source, target, a, b, kind });
    return true;
  };
  const secondaries = nodes.filter((n) => n.role === "secondary");
  secondaries.forEach((s, i) => {
    add(s.id, "hub", s.pos, hub, "hub");
    const next = secondaries[(i + 1) % secondaries.length];
    if (next) add(s.id, next.id, s.pos, next.pos, "hub");
    const mates = nodes.filter((n) => n.role !== "secondary" && (n.clusterId || "") === (s.clusterId || ""));
    const outer = mates.slice().sort((a, b) => Math.hypot(b.pos[0], b.pos[2]) - Math.hypot(a.pos[0], a.pos[2]))[0];
    if (outer) add(outer.id, "hub", outer.pos, hub, "hub");
  });
  for (const n of nodes) {
    if (n.role === "secondary") continue;
    const local = secondaries.find((s) => (s.clusterId || "") === (n.clusterId || "")) ?? secondaries[0];
    if (local) add(n.id, local.id, n.pos, local.pos, "spoke");
  }
  for (const n of nodes) {
    const nearest = nodes
      .filter((o) => o.id !== n.id && (o.clusterId || "") === (n.clusterId || ""))
      .map((o) => ({ o, d: Math.hypot(o.pos[0] - n.pos[0], o.pos[2] - n.pos[2]) }))
      .sort((p, q) => p.d - q.d)
      .slice(0, 2);
    for (const { o } of nearest) add(n.id, o.id, n.pos, o.pos, "near");
  }
  addCrossLinks(nodes, add);
  return edges;
}

/** Facing-edge papers in every cluster pair. About eight links each, all six pairs when four clusters are present. */
function addCrossLinks<T extends Placed>(
  nodes: Drawn<T>[],
  add: (source: string, target: string, a: [number, number, number], b: [number, number, number], kind: NetEdge["kind"]) => boolean,
) {
  const groups = new Map<string, Drawn<T>[]>();
  for (const n of nodes) {
    const list = groups.get(n.clusterId || "") ?? [];
    list.push(n);
    groups.set(n.clusterId || "", list);
  }
  const keys = [...groups.keys()].sort();
  const facing = (list: Drawn<T>[], toward: [number, number, number]) => list
    .filter((n) => n.role !== "secondary")
    .map((n) => ({ n, d: Math.hypot(n.pos[0] - toward[0], n.pos[2] - toward[2]) }))
    .sort((p, q) => p.d - q.d)
    .slice(0, 8)
    .map((p) => p.n);
  for (let i = 0; i < keys.length; i++) {
    for (let j = i + 1; j < keys.length; j++) {
      const a = groups.get(keys[i])!;
      const b = groups.get(keys[j])!;
      const faceA = facing(a, centroid(b));
      const faceB = facing(b, centroid(a));
      if (!faceA.length || !faceB.length) continue;
      let made = 0;
      const room = faceA.length * faceB.length;
      for (let k = 0; made < 8 && k < room; k++) {
        const u = faceA[k % faceA.length];
        const v = faceB[(k * 3 + Math.floor(k / faceA.length)) % faceB.length];
        if (add(u.id, v.id, u.pos, v.pos, "cross")) made++;
      }
    }
  }
}

export function networkLinks(edges: NetEdge[]): TopicLink[] {
  return edges
    .filter((e) => e.source !== "hub" && e.target !== "hub")
    .map((e) => ({ source: e.source, target: e.target, weight: e.kind === "hub" ? 0.8 : 0.45 }));
}
