"use client";
import { useMemo, useState } from "react";
import type { TopicLink } from "@/lib/graph";
import { NODE_BRIGHTNESS, accent, dust as dustColor, gap as gapColor, hub as hubColor, scaleHex } from "@/lib/theme";
import { heroNetwork, neighborIds, networkLinks, nodeAmber, type Star } from "./stars";

/** Flat drawing for reduced motion, low power, or no WebGL. Same amber palette, no drift. */
export function Galaxy2D({ nodes, links, showGaps, focus, highlight, onFocus, onHighlight, onPick }: {
  nodes: (Partial<Star> & Pick<Star, "id" | "support" | "gap">)[]; links: TopicLink[]; showGaps: boolean;
  focus?: string | null; highlight?: Set<string> | null;
  onFocus?: (id: string) => void; onHighlight?: (cluster?: string) => void; onPick?: (id: string) => void;
}) {
  const net = useMemo(() => heroNetwork(nodes), [nodes]);
  const drawn = net.nodes;
  const maxS = Math.max(...drawn.map((n) => n.support), 0.01);
  const [hover, setHover] = useState<string | null>(null);
  const activeId = hover ?? focus ?? null;
  const active = drawn.find((n) => n.id === activeId);
  const near = useMemo(() => {
    if (!hover) return new Set<string>();
    const ids = neighborIds(hover, networkLinks(net.edges));
    for (const id of neighborIds(hover, links)) ids.add(id);
    return ids;
  }, [hover, net.edges, links]);
  const project = (pos: [number, number, number]) => [400 + pos[0] * 30, 280 + pos[2] * 30] as [number, number];
  const hub = project(net.hub);
  const dust = useMemo(() => {
    const specks = [];
    let seed = 11;
    const rand = () => { seed = (seed * 48271) % 2147483647; return (seed % 1000) / 1000; };
    for (let i = 0; i < 520; i++) {
      const a = rand() * Math.PI * 2;
      const r = Math.pow(rand(), 0.65);
      specks.push({ x: 400 + Math.cos(a) * r * 250, y: 280 + Math.sin(a) * r * 175, rad: 1.35 + rand() * 0.85 });
    }
    return specks;
  }, []);
  return (
    <div className="relative h-full w-full">
      <svg viewBox="0 0 800 560" className="h-full w-full" role="img" aria-label="Paper galaxy. Each node is a paper, colored by topic cluster.">
        <defs>
          {drawn.map((n, i) => {
            const hex = showGaps && n.gap ? gapColor : nodeAmber(n.colorIndex, n.clusterId || n.id, n.id);
            return (
              <radialGradient id={`node-halo-${i}`} key={n.id}>
                <stop offset="0%" stopColor={hex} stopOpacity="0.2" />
                <stop offset="42%" stopColor={hex} stopOpacity="0.05" />
                <stop offset="100%" stopColor={hex} stopOpacity="0" />
              </radialGradient>
            );
          })}
        </defs>
        {dust.map((d, i) => <circle key={i} cx={d.x} cy={d.y} r={d.rad} fill={dustColor} opacity={0.9} />)}
        {net.edges.map((edge, i) => {
          const [x1, y1] = project(edge.a);
          const [x2, y2] = project(edge.b);
          const opacity = edge.kind === "hub" ? 0.24 : edge.kind === "spoke" ? 0.18 : edge.kind === "cross" ? 0.1 : 0.14;
          return <line key={`link-${i}`} x1={x1} y1={y1} x2={x2} y2={y2} stroke={accent} strokeOpacity={opacity} strokeWidth={0.7} />;
        })}
        <circle cx={hub[0]} cy={hub[1]} r={15} fill={hubColor} opacity={0.95} />
        {drawn.map((n, i) => {
          const r = n.role === "secondary" ? 11.5 : 7.2 + 3.2 * Math.sqrt(n.support / maxS);
          const gap = showGaps && n.gap;
          const hot = n.id === hover || n.id === focus;
          const lit = hot || near.has(n.id) || highlight?.has(n.id);
          const hex = gap ? gapColor : nodeAmber(n.colorIndex, n.clusterId || n.id, n.id);
          const fill = scaleHex(hex, hot ? 1 : lit ? 0.96 : NODE_BRIGHTNESS);
          const [x, y] = project(n.pos);
          return (
            <g key={n.id} className="cursor-pointer" data-testid={gap ? "gap-node" : "topic-node"}
              onMouseEnter={() => setHover(n.id)} onMouseLeave={() => setHover((h) => (h === n.id ? null : h))}
              onClick={() => { onFocus?.(n.id); if (n.gap) onHighlight?.(n.cluster); }}>
              <circle cx={x} cy={y} r={r * 2.5} fill={`url(#node-halo-${i})`} />
              <circle cx={x} cy={y} r={r} fill={fill} />
            </g>
          );
        })}
      </svg>
      <ul className="sr-only">
        {drawn.map((n) => (
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
