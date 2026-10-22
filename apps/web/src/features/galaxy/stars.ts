import type { TopicLink } from "@/lib/graph";
import { accent, clusterColors, galaxyColor, plexusCopper, plexusGold } from "@/lib/palette";

/** One paper placed in the galaxy, with the cluster fields the shaders read. */
export interface Star {
  id: string;
  /** Paper title. The topics list and the 3D tooltip show this above the topic. */
  title?: string;
  /** OpenAlex display name, when it is distinct from the title. */
  topic?: string;
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

/** Amber shade for one paper. Stays on the cluster ramp, with a small per-paper shift. */
export function nodeAmber(colorIndex: number | null | undefined, clusterId: string, id: string) {
  const base = galaxyColor(colorIndex, clusterId);
  const at = clusterColors.indexOf(base as (typeof clusterColors)[number]);
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h + id.charCodeAt(i)) % 997;
  return clusterColors[((at < 0 ? 0 : at) + (h % 3)) % clusterColors.length];
}

type Vec = [number, number, number];
type Placed = {
  id: string;
  title?: string;
  topic?: string;
  support: number;
  clusterId?: string;
  cluster?: string;
  gap?: boolean;
  colorIndex?: number;
  emerging?: number;
  fresh?: boolean;
  pos?: Vec;
};

/** How many tiny vertices the hero plexus draws. */
export const PLEXUS_COUNT = 310;
/** Neighbours farther than this are not linked. */
export const LINK_REACH = 1.05;

/** Drift, rock, and twinkle, each 1.5× the original plexus motion. */
export const DRIFT_HZ = { x: 0.555, y: 0.435, z: 0.495 } as const;
export const TWINKLE_HZ = 2.55;
/** Continuous yaw around the band centre, radians per second (1.5 × the old 0.16 rock). */
export const ORBIT_SPEED = 0.24;
export const ROCK_X_HZ = 0.18;
export const ROCK_Z_HZ = 0.15;
/** One zoom-in, hold, zoom-out, hold. */
export const BREATH_CYCLE = 14;
/** Resting camera distance and the close end of the breath. */
export const REST_DISTANCE = 22.5;
export const NEAR_DISTANCE = 10.6;
/** World-space shift that parks the band in the right half while zoomed out. */
export const REST_SHIFT = 6.15;
/** Desktop layout: the hero is a left column, so the resting band sits to the right. */
export const WIDE_CANVAS = 1024;
/** Screenshot pin. `in` freezes the close zoom, `out` freezes the resting size. */
export type PlexusPose = "in" | "out" | null;

/** 0 at the resting (right-half) size, 1 at the close zoom. Eases in, holds, eases out, holds. */
export function breathAmount(time: number) {
  const u = ((time % BREATH_CYCLE) + BREATH_CYCLE) % BREATH_CYCLE / BREATH_CYCLE;
  if (u < 0.36) return smoothstep(u / 0.36);
  if (u < 0.52) return 1;
  if (u < 0.88) return 1 - smoothstep((u - 0.52) / 0.36);
  return 0;
}

/** How much larger the band reads. 1 at rest, about 2.1 when breathed in. */
export function zoomScale(breath: number) {
  const ratio = NEAR_DISTANCE / REST_DISTANCE;
  return 1 / (1 + (ratio - 1) * breath);
}

const LEN = 15.6;
const DIR_X = Math.SQRT1_2;
const DIR_Z = -Math.SQRT1_2;
const PER_X = Math.SQRT1_2;
const PER_Z = Math.SQRT1_2;

export type NetRole = "node";
export interface NetEdge {
  source: string;
  target: string;
  a: Vec;
  b: Vec;
  span: number;
  alpha: number;
}

export interface PlexusNode {
  id: string;
  support: number;
  gap: boolean;
  gapScore?: number;
  cluster?: string;
  clusterId: string;
  colorIndex?: number;
  emerging: number;
  fresh?: boolean;
  title?: string;
  topic?: string;
  pos: Vec;
  center: Vec;
  role: NetRole;
  /** 0 at the copper lower-left, 1 at the pale-gold upper-right. */
  t: number;
  phase: number;
  fade: number;
  paper: boolean;
  twinkle: number;
}

/** Copper → amber → pale gold along the band. */
export function plexusTint(t: number) {
  const u = Math.min(1, Math.max(0, t));
  if (u < 0.5) return mixHex(plexusCopper, accent, u * 2);
  return mixHex(accent, plexusGold, (u - 0.5) * 2);
}

/** Near-white core, still tinted by the band. */
export function plexusCore(t: number) {
  return mixHex(plexusTint(t), "#FFF8EE", 0.9);
}

/**
 * Hero drawing. A seeded low-poly plexus: one diagonal band of tiny nodes,
 * each linked only to its nearby neighbours. Real papers are bound onto the band.
 */
export function heroNetwork<T extends Placed>(papers: T[]): { nodes: PlexusNode[]; edges: NetEdge[]; hub: Vec } {
  if (!papers.length) return { nodes: [], edges: [], hub: [0, 0, 0] };
  const rand = mulberry(0x51eed);
  const dots = buildBand(rand);
  const nodes = bindPapers(dots, papers);
  const edges = linkBand(nodes, rand);
  return { nodes, edges, hub: centroid(nodes) };
}

interface Dot { t: number; s: number; pos: Vec; fade: number }

function buildBand(rand: () => number): Dot[] {
  const dots: Dot[] = [];
  const cell = 0.34;
  const grid = new Map<string, number[]>();
  const bucket = (x: number, z: number) => `${Math.floor(x / cell)}:${Math.floor(z / cell)}`;
  let minDist = 0.38;
  let spins = 0;
  while (dots.length < PLEXUS_COUNT && spins < 12) {
    spins++;
    let tries = 0;
    let added = 0;
    while (dots.length < PLEXUS_COUNT && tries < 7000) {
      tries++;
      const t = 0.5 + gauss(rand) * 0.2;
      if (t <= 0.02 || t >= 0.98) continue;
      const s = gauss(rand) * 0.42;
      if (s < -1 || s > 1) continue;
      const edge = 0.8 + 0.04 * Math.sin(t * 2.2 + 0.4);
      const ax = Math.abs(s);
      if (ax > edge) continue;
      if (ax > edge * 0.88 && hash01(t * 4.1, s) > ((edge - ax) / (edge * 0.12)) ** 1.4) continue;
      const y = (rand() - 0.5) * 0.62;
      const pos = place(t, s, y);
      const dist = minDist * (0.72 + 0.55 * (Math.abs(t - 0.5) * 2) + 0.35 * Math.abs(s));
      if (tooClose(dots, grid, cell, pos, dist)) continue;
      const along = Math.exp(-((t - 0.5) ** 2) / 0.12);
      const across = Math.exp(-(s * s) / 0.28);
      const idx = dots.length;
      dots.push({ t, s, pos, fade: 0.34 + 0.66 * Math.min(1, along * 0.7 + across * 0.5) });
      const k = bucket(pos[0], pos[2]);
      const list = grid.get(k);
      if (list) list.push(idx);
      else grid.set(k, [idx]);
      added++;
    }
    if (!added) minDist *= 0.88;
    else minDist *= 0.94;
  }
  return dots;
}

function halfWidth(t: number) {
  const env = Math.sin(Math.PI * Math.min(1, Math.max(0, t))) ** 0.72;
  const blob = 0.76 + 0.24 * Math.sin(t * 8.4 + 0.5) + 0.14 * Math.sin(t * 16.2 + 1.7) + 0.08 * Math.sin(t * 28.0);
  return (0.42 + 3.45 * env) * Math.max(0.4, blob);
}

function centerShift(t: number) {
  return 0.48 * Math.sin(t * 6.3 + 0.6) + 0.26 * Math.sin(t * 14.4 + 2.1);
}

function hash01(a: number, b: number) {
  const n = Math.sin(a * 127.1 + b * 311.7) * 43758.5453;
  return n - Math.floor(n);
}

function place(t: number, s: number, y: number): Vec {
  const along = (t - 0.5) * LEN;
  const across = s * halfWidth(t) + centerShift(t);
  return [DIR_X * along + PER_X * across, y, DIR_Z * along + PER_Z * across];
}

function tooClose(dots: Dot[], grid: Map<string, number[]>, cell: number, pos: Vec, min: number) {
  const min2 = min * min;
  const cx = Math.floor(pos[0] / cell);
  const cz = Math.floor(pos[2] / cell);
  const reach = Math.ceil(min / cell) + 1;
  for (let gx = cx - reach; gx <= cx + reach; gx++) {
    for (let gz = cz - reach; gz <= cz + reach; gz++) {
      const list = grid.get(`${gx}:${gz}`);
      if (!list) continue;
      for (const i of list) {
        const o = dots[i].pos;
        const dx = o[0] - pos[0];
        const dz = o[2] - pos[2];
        if (dx * dx + dz * dz < min2) return true;
      }
    }
  }
  return false;
}

function bindPapers<T extends Placed>(dots: Dot[], papers: T[]): PlexusNode[] {
  const order = dots.map((_, i) => i).sort((a, b) => dots[a].t - dots[b].t || a - b);
  const taken = new Set<number>();
  const bound = new Map<number, T>();
  papers.forEach((paper, i) => {
    const target = Math.round(((i + 0.5) / papers.length) * (order.length - 1));
    for (let hop = 0; hop < order.length; hop++) {
      const step = hop === 0 ? 0 : hop % 2 === 0 ? hop / 2 : -Math.ceil(hop / 2);
      const at = Math.min(order.length - 1, Math.max(0, target + step));
      const idx = order[at];
      if (taken.has(idx)) continue;
      taken.add(idx);
      bound.set(idx, paper);
      break;
    }
  });
  return dots.map((dot, i) => {
    const paper = bound.get(i);
    const phase = ((Math.imul(i + 3, 0x9e3779b1) >>> 0) % 10000) / 10000 * Math.PI * 2;
    const base = {
      pos: dot.pos,
      center: dot.pos,
      role: "node" as const,
      t: dot.t,
      phase,
      fade: dot.fade,
      twinkle: phase % 1 > 0.86 || paper?.fresh ? 1 : 0,
    };
    if (!paper) {
      return {
        ...base,
        id: `dot-${i}`,
        support: 0.2,
        gap: false,
        clusterId: "",
        emerging: 0,
        paper: false,
      };
    }
    return {
      ...base,
      id: paper.id,
      title: paper.title,
      topic: paper.topic,
      support: paper.support,
      gap: !!paper.gap,
      gapScore: undefined,
      cluster: paper.cluster,
      clusterId: paper.clusterId || "",
      colorIndex: paper.colorIndex,
      emerging: paper.emerging ?? 0,
      fresh: paper.fresh,
      paper: true,
      twinkle: (base.twinkle || paper.fresh) ? 1 : 0,
    };
  });
}

function linkBand(nodes: PlexusNode[], rand: () => number): NetEdge[] {
  const cell = LINK_REACH;
  const grid = new Map<string, number[]>();
  const key = (x: number, z: number) => `${Math.floor(x / cell)}:${Math.floor(z / cell)}`;
  nodes.forEach((node, i) => {
    const k = key(node.pos[0], node.pos[2]);
    const list = grid.get(k);
    if (list) list.push(i);
    else grid.set(k, [i]);
  });
  const pairs: { i: number; j: number; d: number }[] = [];
  nodes.forEach((node, i) => {
    const cx = Math.floor(node.pos[0] / cell);
    const cz = Math.floor(node.pos[2] / cell);
    for (let gx = cx - 1; gx <= cx + 1; gx++) {
      for (let gz = cz - 1; gz <= cz + 1; gz++) {
        const bucket = grid.get(`${gx}:${gz}`);
        if (!bucket) continue;
        for (const j of bucket) {
          if (j <= i) continue;
          const d = Math.hypot(node.pos[0] - nodes[j].pos[0], node.pos[2] - nodes[j].pos[2]);
          if (d <= LINK_REACH) pairs.push({ i, j, d });
        }
      }
    }
  });
  pairs.sort((a, b) => a.d - b.d);
  const cap = nodes.map(() => 3 + Math.floor(rand() * 4));
  const deg = nodes.map(() => 0);
  const edges: NetEdge[] = [];
  for (const pair of pairs) {
    if (deg[pair.i] >= cap[pair.i] || deg[pair.j] >= cap[pair.j]) continue;
    deg[pair.i]++;
    deg[pair.j]++;
    const fade = 1 - pair.d / LINK_REACH;
    edges.push({
      source: nodes[pair.i].id,
      target: nodes[pair.j].id,
      a: nodes[pair.i].pos,
      b: nodes[pair.j].pos,
      span: pair.d,
      alpha: 0.14 + 0.4 * fade * fade,
    });
  }
  return edges;
}

/** Same offset the vertex shaders add, so hover stays on the moving node. */
export function plexusDrift(phase: number, time: number, motion: number): Vec {
  if (!motion) return [0, 0, 0];
  return [
    Math.sin(time * DRIFT_HZ.x + phase) * 0.08,
    Math.sin(time * DRIFT_HZ.y + phase * 1.7) * 0.045,
    Math.cos(time * DRIFT_HZ.z + phase * 0.85) * 0.08,
  ];
}

function smoothstep(x: number) {
  const t = Math.min(1, Math.max(0, x));
  return t * t * (3 - 2 * t);
}

function mixHex(a: string, b: string, t: number) {
  const pa = Number.parseInt(a.slice(1), 16);
  const pb = Number.parseInt(b.slice(1), 16);
  const ch = (shift: number) => Math.round(((pa >> shift) & 255) + (((pb >> shift) & 255) - ((pa >> shift) & 255)) * t);
  return `#${[ch(16), ch(8), ch(0)].map((v) => v.toString(16).padStart(2, "0")).join("")}`.toUpperCase();
}

function mulberry(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

function gauss(rand: () => number) {
  const u = Math.max(1e-7, rand());
  const v = rand();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(Math.PI * 2 * v);
}

export function networkLinks(edges: NetEdge[]): TopicLink[] {
  return edges.map((e) => ({ source: e.source, target: e.target, weight: e.alpha }));
}
