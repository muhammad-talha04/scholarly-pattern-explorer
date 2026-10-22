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

/** Orbit around the cluster centre, radians per second. */
export const ORBIT_SPEED = 0.15;
/** Vertical bob, radians per second. */
export const DRIFT_HZ = 0.35;
export const DRIFT_AMP = 0.045;

/** Stable phase so each cluster bobs on its own clock. */
export function phaseOf(id: string) {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h + id.charCodeAt(i) * 17) % 628;
  return h / 100;
}

/**
 * World position after the orbit and the bob. `motion` 0 is the resting layout,
 * used for reduced motion and low power. The instance matrix uses this same
 * point, so a raycast hits the sphere the shader is drawing.
 */
export function posedPosition(
  node: { pos: [number, number, number]; center: [number, number, number]; clusterId: string },
  time: number,
  motion: number,
): [number, number, number] {
  const phase = phaseOf(node.clusterId || "");
  const ax = node.pos[0] - node.center[0];
  const ay = node.pos[1] - node.center[1];
  const az = node.pos[2] - node.center[2];
  const ang = motion * time * ORBIT_SPEED;
  const c = Math.cos(ang);
  const s = Math.sin(ang);
  return [
    node.center[0] + ax * c - az * s,
    node.center[1] + ay + motion * Math.sin(time * DRIFT_HZ + phase) * DRIFT_AMP,
    node.center[2] + ax * s + az * c,
  ];
}
