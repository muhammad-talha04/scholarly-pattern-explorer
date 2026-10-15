"use client";
import { useMemo, useState } from "react";
import type { TopicLink } from "@/lib/graph";
import { NODE_BRIGHTNESS, accent, dust as dustColor, gap as gapColor, galaxyColor, hub as hubColor, scaleHex } from "@/lib/theme";
import { neighborIds, type Star } from "./stars";

/** Flat drawing for reduced motion, low power, or no WebGL. Same amber palette, no drift. */
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
  const project = (pos: [number, number, number]) => [400 + pos[0] * 55, 280 + pos[2] * 36] as [number, number];
  const hub = useMemo(() => {
    if (!nodes.length) return [400, 280] as [number, number];
    let x = 0, y = 0;
    for (const n of nodes) {
      const [px, py] = project(n.pos ?? [0, 0, 0]);
      x += px;
      y += py;
    }
    return [x / nodes.length, y / nodes.length] as [number, number];
  }, [nodes]);
  const dust = useMemo(() => {
    const specks = [];
    let seed = 11;
    const rand = () => { seed = (seed * 48271) % 2147483647; return (seed % 1000) / 1000; };
    for (let i = 0; i < 90; i++) specks.push({ x: 40 + rand() * 720, y: 30 + rand() * 500, r: 0.6 + rand() * 1.1 });
    return specks;
  }, []);
  return (
    <div className="relative h-full w-full">
      <svg viewBox="0 0 800 560" className="h-full w-full" role="img" aria-label="Paper galaxy. Each node is a paper, colored by topic cluster.">
        <defs>
          <radialGradient id="node-halo">
            <stop offset="42%" stopColor={accent} stopOpacity="0" />
            <stop offset="68%" stopColor={accent} stopOpacity="0.42" />
            <stop offset="100%" stopColor={accent} stopOpacity="0" />
          </radialGradient>
        </defs>
        {dust.map((d, i) => <circle key={i} cx={d.x} cy={d.y} r={d.r} fill={dustColor} opacity={0.45} />)}
        {nodes.map((n) => {
          const pos = n.pos ?? [0, 0, 0];
          const [x, y] = project(pos);
          return <line key={`spoke-${n.id}`} x1={x} y1={y} x2={hub[0]} y2={hub[1]} stroke={accent} strokeOpacity={0.32} strokeWidth={0.8} />;
        })}
        <circle cx={hub[0]} cy={hub[1]} r={16} fill={hubColor} opacity={0.95} />
        {nodes.map((n) => {
          const pos = n.pos ?? [0, 0, 0];
          const r = 7 + 15 * Math.sqrt(n.support / maxS);
          const gap = showGaps && n.gap;
          const hot = n.id === hover || n.id === focus;
          const lit = hot || near.has(n.id) || highlight?.has(n.id);
          const hex = gap ? gapColor : galaxyColor(n.colorIndex, n.clusterId || n.id);
          const fill = scaleHex(hex, hot ? 1 : lit ? 0.96 : NODE_BRIGHTNESS);
          const [x, y] = project(pos);
          return (
            <g key={n.id} className="cursor-pointer" data-testid={gap ? "gap-node" : "topic-node"}
              onMouseEnter={() => setHover(n.id)} onMouseLeave={() => setHover((h) => (h === n.id ? null : h))}
              onClick={() => { onFocus?.(n.id); if (n.gap) onHighlight?.(n.cluster); }}>
              <circle cx={x} cy={y} r={r * 2.2} fill="url(#node-halo)" />
              <circle cx={x} cy={y} r={r} fill={fill} />
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
