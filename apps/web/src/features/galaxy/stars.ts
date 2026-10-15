import type { TopicLink } from "@/lib/graph";

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
/** Hero drawing cap. Graphs of 14 or fewer are shown whole. */
const CONSTELLATION_CAP = 12;

type Placed = { id: string; support: number; clusterId?: string; gap?: boolean; pos?: [number, number, number] };

/**
 * The landing drawing is a dozen distinct papers, not the full catalogue.
 * Highest-support papers are taken round-robin by cluster, then seated on a
 * golden spiral so the spheres stay separated around the hub.
 */
export function heroConstellation<T extends Placed>(nodes: T[]): (T & { pos: [number, number, number] })[] {
  const picked = nodes.length > 14 ? pickConstellation(nodes) : nodes.slice();
  return placeConstellation(picked);
}

function pickConstellation<T extends Placed>(nodes: T[]): T[] {
  const groups = new Map<string, T[]>();
  for (const n of nodes) {
    const key = n.clusterId || "";
    const list = groups.get(key) ?? [];
    list.push(n);
    groups.set(key, list);
  }
  for (const list of groups.values()) list.sort((a, b) => b.support - a.support || a.id.localeCompare(b.id));
  const picked: T[] = [];
  const seen = new Set<string>();
  const take = (n: T) => {
    if (picked.length >= CONSTELLATION_CAP || seen.has(n.id)) return;
    seen.add(n.id);
    picked.push(n);
  };
  const gap = nodes.filter((n) => n.gap).sort((a, b) => b.support - a.support || a.id.localeCompare(b.id))[0];
  if (gap) take(gap);
  const keys = [...groups.keys()];
  let round = 0;
  while (picked.length < CONSTELLATION_CAP) {
    let added = false;
    for (const key of keys) {
      const list = groups.get(key)!;
      if (round < list.length) {
        take(list[round]);
        added = true;
        if (picked.length >= CONSTELLATION_CAP) break;
      }
    }
    if (!added) break;
    round++;
  }
  return picked;
}

function placeConstellation<T extends Placed>(nodes: T[]): (T & { pos: [number, number, number] })[] {
  const n = nodes.length;
  return nodes.map((node, i) => {
    const t = n <= 1 ? 0 : i / (n - 1);
    const r = n <= 1 ? 3.4 : 2.7 + t * 3.15;
    const a = i * GOLDEN;
    const y = (((i * 7919) % 13) / 13 - 0.5) * 0.85;
    const pos: [number, number, number] = [r * Math.cos(a), y, r * Math.sin(a)];
    return { ...node, pos, center: pos };
  });
}
