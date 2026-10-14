"use client";
import { useMemo } from "react";
import type { TopicLink, TopicNode } from "@/lib/graph";
import { linkPairs, positionNodes } from "./layout";

/** Static SVG fallback for reduced motion / low power / no WebGL. */
export function Galaxy2D({ nodes, links, showGaps, onPick }: { nodes: TopicNode[]; links: TopicLink[]; showGaps: boolean; onPick?: (id: string) => void }) {
  const placed = useMemo(() => positionNodes(nodes), [nodes]);
  const pairs = useMemo(() => linkPairs(placed, links), [placed, links]);
  const maxS = Math.max(...nodes.map((n) => n.support), 0.01);
  const X = (v: number) => 400 + v * 55, Y = (v: number) => 260 + v * 38;
  return (
    <svg viewBox="0 0 800 520" className="h-full w-full" role="img" aria-label="Topic galaxy (2D)">
      {pairs.map(({ a, b, w }, i) => <line key={i} x1={X(a.pos[0])} y1={Y(a.pos[2])} x2={X(b.pos[0])} y2={Y(b.pos[2])} stroke="#7dd3fc" strokeOpacity={0.25} strokeWidth={0.5 + w * 8} />)}
      {placed.map((n) => {
        const r = 5 + 18 * Math.sqrt(n.support / maxS), gap = showGaps && n.gap;
        return (
          <g key={n.id} onClick={() => onPick?.(n.id)} className="cursor-pointer" data-testid={gap ? "gap-node" : "topic-node"}>
            {gap && <circle cx={X(n.pos[0])} cy={Y(n.pos[2])} r={r * 1.8} fill="#f472b6" opacity={0.15} />}
            <circle cx={X(n.pos[0])} cy={Y(n.pos[2])} r={r} fill={gap ? "#f472b6" : "#a78bfa"} opacity={0.9} />
            <text x={X(n.pos[0])} y={Y(n.pos[2]) - r - 4} textAnchor="middle" fontSize={11} fill={gap ? "#fbcfe8" : "#cbd5e1"}>{n.id}</text>
          </g>
        );
      })}
    </svg>
  );
}
