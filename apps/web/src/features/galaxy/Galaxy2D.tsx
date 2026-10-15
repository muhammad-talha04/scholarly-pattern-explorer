"use client";
import { useMemo, useState } from "react";
import type { TopicLink, TopicNode } from "@/lib/graph";
import { linkPairs, positionNodes, type Positioned } from "./layout";

const PALETTE = ["#7dd3fc", "#c4b5fd", "#6ee7b7", "#fcd34d", "#fb923c", "#f9a8d4"];
function colorFor(n: { id: string; cluster?: string; gap: boolean }, showGaps: boolean) {
  if (showGaps && n.gap) return "#f9a8d4";
  const key = n.cluster ?? n.id;
  let h = 0;
  for (let i = 0; i < key.length; i++) h = (h + key.charCodeAt(i) * 13) % PALETTE.length;
  return PALETTE[h];
}

/** Flat drawing for reduced motion, low power, or no WebGL. */
export function Galaxy2D({ nodes, links, showGaps, focus, onFocus, onPick }: {
  nodes: (TopicNode & { pos?: [number, number, number] })[]; links: TopicLink[]; showGaps: boolean;
  focus?: string | null; onFocus?: (id: string) => void; onPick?: (id: string) => void;
}) {
  const placed = useMemo(() => (nodes.some((n) => n.pos) ? nodes as Positioned[] : positionNodes(nodes)), [nodes]);
  const pairs = useMemo(() => linkPairs(placed, links), [placed, links]);
  const maxS = Math.max(...nodes.map((n) => n.support), 0.01);
  const [hover, setHover] = useState<string | null>(null);
  const activeId = hover ?? focus ?? null;
  const active = placed.find((n) => n.id === activeId);
  const X = (v: number) => 400 + v * 55, Y = (v: number) => 280 + v * 36;
  return (
    <div className="relative h-full w-full">
      <svg viewBox="0 0 800 560" className="h-full w-full" role="img" aria-label="Paper galaxy. Each dot is a paper, colored by topic cluster.">
        {pairs.map(({ a, b, w }, i) => <line key={i} x1={X(a.pos[0])} y1={Y(a.pos[2])} x2={X(b.pos[0])} y2={Y(b.pos[2])} stroke="#7dd3fc" strokeOpacity={0.28} strokeWidth={0.6 + w * 7} />)}
        {placed.map((n) => {
          const r = 6 + 16 * Math.sqrt(n.support / maxS);
          const gap = showGaps && n.gap;
          return (
            <g key={n.id} className="cursor-pointer" data-testid={gap ? "gap-node" : "topic-node"}
              onMouseEnter={() => setHover(n.id)} onMouseLeave={() => setHover((h) => (h === n.id ? null : h))}
              onClick={() => onFocus?.(n.id)}>
              {gap && <circle cx={X(n.pos[0])} cy={Y(n.pos[2])} r={r * 1.8} fill="#f9a8d4" opacity={0.16} />}
              <circle cx={X(n.pos[0])} cy={Y(n.pos[2])} r={r} fill={colorFor(n, showGaps)} opacity={0.95} />
            </g>
          );
        })}
      </svg>
      <ul className="sr-only">
        {placed.map((n) => (
          <li key={n.id}><button onClick={() => { onFocus?.(n.id); onPick?.(n.id); }}>{n.id}, paper{n.cluster ? `, topic cluster ${n.cluster}` : ""}{showGaps && n.gap ? ", research gap" : ""}</button></li>
        ))}
      </ul>
      {active && (
        <div className="glass absolute left-3 top-24 z-10 w-52 p-3 text-xs sm:left-auto sm:right-4" role="tooltip">
          <p className="font-medium text-white">{active.id}</p>
          <p className="mt-1 text-mist">Paper{active.cluster ? ` · topic cluster ${active.cluster}` : ""}</p>
          {showGaps && active.gap && <p className="text-pink-200">Research gap</p>}
          <button className="btn mt-2 w-full py-1" onClick={() => onPick?.(active.id)}>Search this paper</button>
        </div>
      )}
    </div>
  );
}
