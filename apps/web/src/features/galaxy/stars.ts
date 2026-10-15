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

/** Above this, the hero keeps a round-robin sample so the disc stays readable. */
const NETWORK_CAP = 56;
const DISC = 8.7;

type Vec = [number, number, number];
type Placed = { id: string; support: number; clusterId?: string; gap?: boolean; pos?: Vec };

export type NetRole = "hub" | "junction";
export interface NetEdge {
  source: string;
  target: string;
  a: Vec;
  b: Vec;
  kind: "filament";
}

export interface FilamentPoint {
  pos: Vec;
  depth: number;
  along: number;
  pulse: number;
  phase: number;
}

export interface Filament {
  kind: "bridge" | "branch";
  pts: FilamentPoint[];
}

export interface Speck {
  pos: Vec;
  depth: number;
  bright?: boolean;
}

/** Amber shade for one paper. Stays on the cluster ramp, with a small per-paper shift. */
export function nodeAmber(colorIndex: number | null | undefined, clusterId: string, id: string) {
  const base = galaxyColor(colorIndex, clusterId);
  const at = clusterColors.indexOf(base as (typeof clusterColors)[number]);
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h + id.charCodeAt(i)) % 997;
  return clusterColors[((at < 0 ? 0 : at) + (h % 3)) % clusterColors.length];
}

type Drawn<T> = T & { pos: Vec; center: Vec; role: NetRole; hubRank?: number };

/** Irregular soma positions spread across the disc, with open space between them. */
const HUB_SLOTS: Vec[] = [
  [-5.9, 0.03, -2.6],
  [4.7, -0.05, -6.1],
  [2.5, 0.04, -0.7],
  [6.5, 0.0, 3.3],
  [-6.7, 0.06, 4.4],
  [-0.3, -0.04, 7.0],
];

interface RawPoint { pos: Vec; depth: number }
interface RawFilament { kind: "bridge" | "branch"; pts: RawPoint[]; hubIds: string[] }

/**
 * Hero drawing. Up to 56 papers on an organic web: a handful of glowing hubs
 * joined by curved filaments, with the other papers at the branch points.
 */
export function heroNetwork<T extends Placed>(nodes: T[]): {
  nodes: Drawn<T>[]; edges: NetEdge[]; filaments: Filament[]; specks: Speck[]; hub: Vec;
} {
  const picked = nodes.length > NETWORK_CAP ? pickNetwork(nodes) : nodes.slice();
  if (!picked.length) return { nodes: [], edges: [], filaments: [], specks: [], hub: [0, 0, 0] };
  return growWeb(picked);
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

function growWeb<T extends Placed>(nodes: T[]): {
  nodes: Drawn<T>[]; edges: NetEdge[]; filaments: Filament[]; specks: Speck[]; hub: Vec;
} {
  const want = nodes.length >= 8 ? 6 : Math.max(1, Math.min(6, nodes.length));
  const chosen = chooseHubs(nodes, want);
  const hubIds = new Set(chosen.map((n) => n.id));
  const drawn: Drawn<T>[] = chosen.map((node, i) => ({
    ...node,
    pos: HUB_SLOTS[i] ?? HUB_SLOTS[0],
    center: HUB_SLOTS[i] ?? HUB_SLOTS[0],
    role: "hub" as const,
    hubRank: i,
  }));
  const built = buildFilaments(drawn);
  const raw = built.filaments;
  const spots = paperSpots(built.junctions, raw);
  const rest = nodes.filter((n) => !hubIds.has(n.id)).sort((a, b) => b.support - a.support || a.id.localeCompare(b.id));
  const occupied: Vec[] = drawn.map((n) => n.pos);
  const hubPos = drawn.map((n) => n.pos);
  for (const node of rest) {
    const spot = spots.find((p) => hubPos.every((o) => dist2(o, p) > 0.85) && occupied.every((o) => dist2(o, p) > 0.46));
    const chosen = spot ?? farthest(spots, occupied) ?? drawn[0].pos;
    const at = spots.indexOf(chosen);
    if (at >= 0) spots.splice(at, 1);
    const pos = clampDisc(chosen);
    occupied.push(pos);
    const placed: Drawn<T> = { ...node, pos, center: pos, role: "junction" };
    drawn.push(placed);
  }
  const filaments = decorate(raw);
  const edges = papersAlong(filaments, drawn);
  const specks = sprinkle(filaments, drawn, built.junctions);
  const primary = drawn.find((n) => n.hubRank === 0) ?? drawn[0];
  return { nodes: drawn, edges, filaments, specks, hub: primary.pos };
}

function chooseHubs<T extends Placed>(nodes: T[], want: number): T[] {
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
    if (picked.length >= want || seen.has(n.id)) return;
    seen.add(n.id);
    picked.push(n);
  };
  const ranked = nodes.slice().sort((a, b) => b.support - a.support || a.id.localeCompare(b.id));
  if (ranked[0]) take(ranked[0]);
  const keys = [...groups.keys()].sort();
  let round = 0;
  while (picked.length < want) {
    let added = false;
    for (const key of keys) {
      const list = groups.get(key)!;
      if (round < list.length) {
        take(list[round]);
        added = true;
      }
      if (picked.length >= want) break;
    }
    if (!added) break;
    round++;
  }
  picked.sort((a, b) => b.support - a.support || a.id.localeCompare(b.id));
  return picked;
}

function buildFilaments<T extends Drawn<Placed>>(hubs: T[]): { filaments: RawFilament[]; junctions: Vec[] } {
  const out: RawFilament[] = [];
  const junctions: Vec[] = [];
  const linked = new Set<string>();
  const pairKey = (a: string, b: string) => [a, b].sort().join("|");
  const neighboursOf = (hub: T) => hubs
    .filter((other) => other.id !== hub.id)
    .map((other) => ({ other, d: dist2(hub.pos, other.pos) }))
    .sort((a, b) => a.d - b.d)
    .slice(0, Math.min(3, Math.max(0, hubs.length - 1)))
    .map((item) => item.other);
  hubs.forEach((hub) => {
    for (const other of neighboursOf(hub)) {
      const key = pairKey(hub.id, other.id);
      if (linked.has(key)) continue;
      linked.add(key);
      out.push(bridge(hub, other, hash(`${hub.id}|${other.id}`)));
    }
  });
  hubs.forEach((hub) => {
    const rand = mulberry(hash(hub.id) + 19);
    const neighbours = neighboursOf(hub);
    const angles: number[] = neighbours.map((other) => Math.atan2(other.pos[2] - hub.pos[2], other.pos[0] - hub.pos[0]) + (rand() - 0.5) * 0.45);
    const count = hubs.length < 3 ? 4 : 8 + Math.floor(rand() * 7);
    let spins = 0;
    while (angles.length < count && spins < 80) {
      spins++;
      const ang = rand() * Math.PI * 2;
      if (angles.some((a) => Math.abs(Math.atan2(Math.sin(ang - a), Math.cos(ang - a))) < 0.34)) continue;
      angles.push(ang);
    }
    angles.forEach((ang, i) => {
      const aim = i < neighbours.length ? neighbours[i] : null;
      out.push(...dendrite(hub, hub.pos, 0.02, [Math.cos(ang), Math.sin(ang)], aim, rand, 0, junctions));
    });
  });
  return { filaments: out, junctions };
}

function bridge<T extends { id: string; pos: Vec }>(a: T, b: T, seed: number): RawFilament {
  const rand = mulberry(seed);
  const dx = b.pos[0] - a.pos[0];
  const dz = b.pos[2] - a.pos[2];
  const len = Math.hypot(dx, dz) || 1;
  const px = -dz / len;
  const pz = dx / len;
  const sign = rand() < 0.5 ? -1 : 1;
  const ctrl: Vec[] = [];
  const n = 6;
  for (let i = 0; i <= n; i++) {
    const t = i / n;
    const bow = Math.sin(t * Math.PI) * Math.min(1.7, Math.max(0.55, len * 0.18)) * sign;
    const wave = Math.sin(t * Math.PI * 2.15 + rand() * 4) * Math.min(0.55, len * 0.06);
    const y = a.pos[1] * (1 - t) + b.pos[1] * t + Math.sin(t * Math.PI) * (rand() - 0.5) * 0.28;
    ctrl.push(clampDisc([
      a.pos[0] * (1 - t) + b.pos[0] * t + px * (bow + wave),
      y,
      a.pos[2] * (1 - t) + b.pos[2] * t + pz * (bow + wave),
    ]));
  }
  ctrl[0] = a.pos;
  ctrl[n] = b.pos;
  const curve = catmull(ctrl, 4);
  const pts = curve.map((pos, i) => {
    const t = i / Math.max(1, curve.length - 1);
    return { pos, depth: Math.sin(t * Math.PI) };
  });
  return { kind: "bridge", pts, hubIds: [a.id, b.id] };
}

function dendrite<T extends { id: string; pos: Vec }>(
  origin: T,
  start: Vec,
  startDepth: number,
  dir: [number, number],
  aim: T | null,
  rand: () => number,
  gen: number,
  splits: Vec[],
): RawFilament[] {
  const pts: RawPoint[] = [{ pos: start, depth: startDepth }];
  let p = start;
  let d = dir;
  const aimed = aim ? Math.max(dist2(start, aim.pos) * 1.08, 2.4) : 0;
  const reach = gen === 0
    ? (aim ? aimed : rand() < 0.4 ? 3.4 + rand() * 1.8 : 6.4 + rand() * 2.2)
    : gen === 1 ? 2.4 + rand() * 1.8 : 1.3 + rand() * 1.2;
  const step = 0.42;
  const splitAt = gen === 0 ? [0.32, 0.62] : gen === 1 ? [0.5] : [];
  let splitIdx = 0;
  const children: RawFilament[] = [];
  let guard = 0;
  let joined: T | null = null;
  const limit = Math.ceil(reach / step) + 1;
  while (guard < limit && guard < 28) {
    guard++;
    const turn = (rand() - 0.5) * (gen === 0 ? 0.32 : 0.7);
    if (aim && gen === 0) {
      const toward = Math.atan2(aim.pos[2] - p[2], aim.pos[0] - p[0]);
      const heading = Math.atan2(d[1], d[0]);
      let delta = toward - heading;
      while (delta > Math.PI) delta -= Math.PI * 2;
      while (delta < -Math.PI) delta += Math.PI * 2;
      d = rot(d, delta * 0.28 + turn);
    } else d = rot(d, turn);
    p = clampDisc([p[0] + d[0] * step, p[1] + (rand() - 0.5) * 0.04, p[2] + d[1] * step]);
    const depth = Math.min(0.98, startDepth + (guard * step) / reach);
    pts.push({ pos: p, depth });
    if (splitIdx < splitAt.length && guard * step >= splitAt[splitIdx] * reach) {
      splitIdx++;
      splits.push(p);
      const spin = (rand() < 0.5 ? -1 : 1) * (0.45 + rand() * 0.5);
      children.push(...dendrite(origin, p, depth, rot(d, spin), null, rand, gen + 1, splits));
    }
    if (aim && guard * step > reach * 0.4 && dist2(p, aim.pos) < 0.9) {
      pts.push({ pos: aim.pos, depth: 0.04 });
      joined = aim;
      break;
    }
  }
  if (joined) {
    const tail = Math.max(2, Math.floor(pts.length * 0.28));
    for (let i = pts.length - tail; i < pts.length; i++) {
      const t = (i - (pts.length - tail)) / Math.max(1, tail - 1);
      pts[i].depth *= 1 - t;
    }
    pts[pts.length - 1].depth = 0;
  }
  const self: RawFilament = { kind: "branch", pts, hubIds: joined ? [origin.id, joined.id] : [origin.id] };
  return [self, ...children];
}

function paperSpots(junctions: Vec[], fils: RawFilament[]): Vec[] {
  const spots = junctions.map((p) => p.slice() as Vec);
  const rand = mulberry(91);
  fils.forEach((filament, index) => {
    if (filament.pts.length < 8) return;
    const picks = filament.pts.length > 28 ? 2 : 1;
    for (let n = 0; n < picks; n++) {
      const i = 3 + Math.floor(mulberry(hash(`s${index}-${n}`))() * (filament.pts.length - 6));
      spots.push(filament.pts[i].pos);
    }
  });
  for (let i = spots.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    const swap = spots[i];
    spots[i] = spots[j];
    spots[j] = swap;
  }
  return spots;
}

function decorate(raw: RawFilament[]): Filament[] {
  return raw.filter((f) => f.pts.length > 1).map((f, index) => {
    const pulse = f.kind === "bridge" || index % 2 === 0 ? 1 : 0;
    const phase = (index * 0.173) % 1;
    const pts = f.pts.map((p, i) => ({
      pos: p.pos,
      depth: p.depth,
      along: i / Math.max(1, f.pts.length - 1),
      pulse,
      phase,
    }));
    return { kind: f.kind, pts };
  });
}

function papersAlong<T extends Drawn<Placed>>(filaments: Filament[], nodes: T[]): NetEdge[] {
  const edges: NetEdge[] = [];
  const seen = new Set<string>();
  for (const f of filaments) {
    const on = nodes
      .map((n) => ({ n, along: closestAlong(f, n.pos) }))
      .filter((item) => item.along.dist < 0.42)
      .sort((a, b) => a.along.t - b.along.t);
    for (let i = 1; i < on.length; i++) {
      const a = on[i - 1].n;
      const b = on[i].n;
      const key = [a.id, b.id].sort().join("|");
      if (a.id === b.id || seen.has(key)) continue;
      seen.add(key);
      edges.push({ source: a.id, target: b.id, a: a.pos, b: b.pos, kind: "filament" });
    }
  }
  return edges;
}

function closestAlong(f: Filament, pos: Vec) {
  let best = { dist: Infinity, t: 0 };
  f.pts.forEach((p, i) => {
    const dist = dist2(p.pos, pos);
    if (dist < best.dist) best = { dist, t: p.along || i / Math.max(1, f.pts.length - 1) };
  });
  return best;
}

function sprinkle<T extends { pos: Vec }>(filaments: Filament[], papers: T[], junctions: Vec[]): Speck[] {
  const out: Speck[] = [];
  for (const joint of junctions) {
    if (papers.some((p) => dist2(p.pos, joint) < 0.28)) continue;
    out.push({ pos: joint, depth: 0.12, bright: true });
  }
  for (const f of filaments) {
    for (let i = 1; i < f.pts.length; i += 2) {
      const a = f.pts[i - 1];
      const b = f.pts[i];
      const pos = clampDisc(lerp(a.pos, b.pos, 0.5));
      if (papers.some((p) => dist2(p.pos, pos) < 0.3)) continue;
      if (out.some((s) => dist2(s.pos, pos) < 0.22)) continue;
      out.push({ pos, depth: (a.depth + b.depth) / 2, bright: false });
      if (out.length >= 720) return out;
    }
  }
  return out;
}

function catmull(pts: Vec[], samples: number): Vec[] {
  const out: Vec[] = [];
  const at = (i: number) => pts[Math.max(0, Math.min(pts.length - 1, i))];
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = at(i - 1);
    const p1 = at(i);
    const p2 = at(i + 1);
    const p3 = at(i + 2);
    for (let s = 0; s < samples; s++) {
      const t = s / samples;
      const t2 = t * t;
      const t3 = t2 * t;
      out.push([
        0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3),
        0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3),
        0.5 * ((2 * p1[2]) + (-p0[2] + p2[2]) * t + (2 * p0[2] - 5 * p1[2] + 4 * p2[2] - p3[2]) * t2 + (-p0[2] + 3 * p1[2] - 3 * p2[2] + p3[2]) * t3),
      ]);
    }
  }
  out.push(pts[pts.length - 1]);
  return out;
}

function mulberry(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

function hash(text: string) {
  let h = 2166136261;
  for (let i = 0; i < text.length; i++) h = Math.imul(h ^ text.charCodeAt(i), 16777619);
  return h >>> 0;
}

function dist2(a: Vec, b: Vec) {
  return Math.hypot(a[0] - b[0], a[2] - b[2]);
}

function lerp(a: Vec, b: Vec, t: number): Vec {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
}

function rot(d: [number, number], ang: number): [number, number] {
  const c = Math.cos(ang);
  const s = Math.sin(ang);
  const x = d[0] * c - d[1] * s;
  const z = d[0] * s + d[1] * c;
  const len = Math.hypot(x, z) || 1;
  return [x / len, z / len];
}

function clampDisc(p: Vec): Vec {
  const d = Math.hypot(p[0], p[2]) || 0.001;
  if (d <= DISC) return p;
  const s = DISC / d;
  return [p[0] * s, p[1], p[2] * s];
}

function farthest(spots: Vec[], occupied: Vec[]): Vec | null {
  let best: Vec | null = null;
  let bestD = -1;
  for (const spot of spots) {
    const d = Math.min(...occupied.map((o) => dist2(o, spot)));
    if (d > bestD) { bestD = d; best = spot; }
  }
  return best;
}

export function networkLinks(edges: NetEdge[]): TopicLink[] {
  return edges
    .filter((e) => e.source !== "hub" && e.target !== "hub")
    .map((e) => ({ source: e.source, target: e.target, weight: 0.5 }));
}
