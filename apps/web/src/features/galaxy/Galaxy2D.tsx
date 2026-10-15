"use client";
import { useMemo, useState } from "react";
import type { TopicLink } from "@/lib/graph";
import { NODE_BRIGHTNESS, accent, gap as gapColor, galaxyColor, ink, linkGrey, scaleHex } from "@/lib/theme";
import { neighborIds, type Star } from "./stars";

/** Flat drawing for reduced motion, low power, or no WebGL. Nodes stay sharp. */
export function Galaxy2D({ nodes, links, showGaps, focus, highlight, onFocus, onHighlight, onPick }: {
  nodes: (Partial<Star> & Pick<Star, "id" | "support" | "gap">)[]; links: TopicLink[]; showGaps: boolean;
  focus?: string | null; highlight?: Set<string> | null;
  onFocus?: (id: string) => void; onHighlight?: (cluster?: string) => void; onPick?: (id: string) => void;
}) {
  const maxS = Math.max(...nodes.map((n) => n.support), 0.01);
  const [hover, setHover] = useState<string | null>(null);
  const activeId = hover ?? focus ?? null;
  const active = nodes.find((n) => n.id === activeId);
  const near = useMemo(() => (hover ? neighborIds(hover, links) : new Set<string>()), [hover, links]);
  const X = (v: number) => 400 + v * 55, Y = (v: number) => 280 + v * 36;
  return (
    <div className="relative h-full w-full">
      <svg viewBox="0 0 800 560" className="h-full w-full" role="img" aria-label="Paper galaxy. Each dot is a paper, colored by topic cluster.">
        {links.map((l, i) => {
          const a = nodes.find((n) => n.id === l.source), b = nodes.find((n) => n.id === l.target);
          if (!a?.pos || !b?.pos) return null;
          return <line key={i} x1={X(a.pos[0])} y1={Y(a.pos[2])} x2={X(b.pos[0])} y2={Y(b.pos[2])} stroke={linkGrey} strokeOpacity={0.2} strokeWidth={0.8} />;
        })}
        {nodes.map((n) => {
          const pos = n.pos ?? [0, 0, 0];
          const r = 6 + 16 * Math.sqrt(n.support / maxS);
          const gap = showGaps && n.gap;
          const hot = n.id === hover || n.id === focus;
          const lit = hot || near.has(n.id) || highlight?.has(n.id);
          const hex = gap ? gapColor : galaxyColor(n.colorIndex, n.clusterId || n.id);
          const fill = scaleHex(hex, hot ? 1 : lit ? 0.94 : NODE_BRIGHTNESS);
          return (
            <g key={n.id} className="cursor-pointer" data-testid={gap ? "gap-node" : "topic-node"}
              onMouseEnter={() => setHover(n.id)} onMouseLeave={() => setHover((h) => (h === n.id ? null : h))}
              onClick={() => { onFocus?.(n.id); if (n.gap) onHighlight?.(n.cluster); }}>
              <circle cx={X(pos[0]) + 2} cy={Y(pos[2]) + 3} r={r * 0.72} fill={ink} opacity={0.35} />
              <circle cx={X(pos[0])} cy={Y(pos[2])} r={r} fill={fill} stroke={accent} strokeOpacity={0.28} strokeWidth={0.7} />
            </g>
          );
        })}
      </svg>
      <ul className="sr-only">
        {nodes.map((n) => (
          <li key={n.id}><button onClick={() => { onFocus?.(n.id); onPick?.(n.id); }}>{n.id}, paper{n.cluster ? `, topic cluster ${n.cluster}` : ""}{showGaps && n.gap ? ", research gap" : ""}</button></li>
        ))}
      </ul>
      {active && (
        <div className="glass absolute left-3 top-24 z-10 w-52 p-3 text-xs sm:left-auto sm:right-4" role="tooltip">
          <p className="font-medium text-white">{active.id}</p>
          <p className="mt-1 text-mist">Paper{active.cluster ? ` · topic cluster ${active.cluster}` : ""}</p>
          {showGaps && active.gap && <p className="text-gap">Research gap</p>}
          <button className="btn mt-2 w-full py-1" onClick={() => onPick?.(active.id)}>Search this paper</button>
        </div>
      )}
    </div>
  );
}
