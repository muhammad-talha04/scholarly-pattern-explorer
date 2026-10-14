import type { TopicNode, TopicLink } from "@/lib/graph";
/** Deterministic spiral-galaxy positions (fibonacci sphere flattened into a disc). */
export function positionNodes(nodes: TopicNode[], radius = 6) {
  const golden = Math.PI * (3 - Math.sqrt(5));
  return nodes.map((n, i) => {
    const r = radius * Math.sqrt((i + 0.5) / nodes.length), a = i * golden;
    return { ...n, pos: [r * Math.cos(a), (((i * 7919) % 13) / 13 - 0.5) * 1.6, r * Math.sin(a)] as [number, number, number] };
  });
}
export type Positioned = ReturnType<typeof positionNodes>[number];
export function linkPairs(nodes: Positioned[], links: TopicLink[]) {
  const by = new Map(nodes.map((n) => [n.id, n]));
  return links.flatMap((l) => { const a = by.get(l.source), b = by.get(l.target); return a && b ? [{ a, b, w: l.weight }] : []; });
}
