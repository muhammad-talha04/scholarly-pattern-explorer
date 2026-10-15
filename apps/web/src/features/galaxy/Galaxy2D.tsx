"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import type { TopicLink } from "@/lib/graph";
import { gap as gapColor, ink } from "@/lib/theme";
import { heroNetwork, neighborIds, networkLinks, plexusCore, plexusTint, type Star } from "./stars";

/** Flat plexus for reduced motion, low power, or no WebGL. Same band, no drift. */
export function Galaxy2D({ nodes, links, showGaps, focus, highlight, onFocus, onHighlight, onPick }: {
  nodes: (Partial<Star> & Pick<Star, "id" | "support" | "gap">)[]; links: TopicLink[]; showGaps: boolean;
  focus?: string | null; highlight?: Set<string> | null;
  onFocus?: (id: string) => void; onHighlight?: (cluster?: string) => void; onPick?: (id: string) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const net = useMemo(() => heroNetwork(nodes), [nodes]);
  const [hover, setHover] = useState<string | null>(null);
  const activeId = hover ?? focus ?? null;
  const active = net.nodes.find((n) => n.paper && n.id === activeId);
  const near = useMemo(() => {
    if (!hover) return new Set<string>();
    const ids = neighborIds(hover, networkLinks(net.edges));
    for (const id of neighborIds(hover, links)) ids.add(id);
    return ids;
  }, [hover, net.edges, links]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const parent = canvas.parentElement;
    if (!parent || typeof ResizeObserver === "undefined") return;
    const draw = () => {
      const rect = parent.getBoundingClientRect();
      const w = Math.max(1, Math.floor(rect.width));
      const h = Math.max(1, Math.floor(rect.height));
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
      }
      let ctx: CanvasRenderingContext2D | null = null;
      try { ctx = canvas.getContext("2d"); } catch { ctx = null; }
      if (!ctx) return;
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = ink;
      ctx.fillRect(0, 0, w, h);
      const unit = Math.min(w, h) / 18.5;
      const project = (pos: [number, number, number]) => [w * 0.5 + pos[0] * unit, h * 0.52 + pos[2] * unit] as [number, number];
      const hub = project(net.hub);
      const wash = ctx.createRadialGradient(hub[0], hub[1], 0, hub[0], hub[1], unit * 4.2);
      wash.addColorStop(0, "rgba(245, 165, 74, 0.20)");
      wash.addColorStop(0.45, "rgba(253, 231, 176, 0.06)");
      wash.addColorStop(1, "rgba(245, 165, 74, 0)");
      ctx.fillStyle = wash;
      ctx.beginPath();
      ctx.arc(hub[0], hub[1], unit * 4.2, 0, Math.PI * 2);
      ctx.fill();
      const tintAt = new Map(net.nodes.map((n) => [n.id, n.t]));
      for (const edge of net.edges) {
        const [x1, y1] = project(edge.a);
        const [x2, y2] = project(edge.b);
        const hot = edge.source === hover || edge.target === hover || near.has(edge.source) || near.has(edge.target);
        ctx.strokeStyle = hexAlpha(plexusTint(tintAt.get(edge.source) ?? 0.5), hot ? Math.min(0.85, edge.alpha * 2.2) : edge.alpha);
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
      }
      for (const node of net.nodes) {
        const [x, y] = project(node.pos);
        const hot = node.id === hover || node.id === focus || near.has(node.id) || highlight?.has(node.id);
        const tint = plexusTint(node.t);
        const core = showGaps && node.gap ? gapColor : plexusCore(node.t);
        ctx.globalAlpha = Math.min(1, node.fade * (hot ? 1 : 0.92));
        ctx.fillStyle = hexAlpha(tint, 0.28);
        ctx.beginPath();
        ctx.arc(x, y, hot ? 4.2 : 3.1, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = core;
        ctx.beginPath();
        ctx.arc(x, y, hot ? 2.1 : 1.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.globalAlpha = 1;
      }
    };
    draw();
    const observer = new ResizeObserver(draw);
    observer.observe(parent);
    return () => observer.disconnect();
  }, [net, hover, focus, highlight, near, showGaps]);

  const pick = (ev: { clientX: number; clientY: number }) => {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const unit = Math.min(rect.width, rect.height) / 18.5;
    const px = ev.clientX - rect.left;
    const py = ev.clientY - rect.top;
    let best: string | null = null;
    let bestD = 12 * 12;
    for (const node of net.nodes) {
      const x = rect.width * 0.5 + node.pos[0] * unit;
      const y = rect.height * 0.52 + node.pos[2] * unit;
      const dd = (x - px) ** 2 + (y - py) ** 2;
      if (dd < bestD) { bestD = dd; best = node.id; }
    }
    return best;
  };

  return (
    <div className="relative h-full w-full">
      <canvas
        ref={canvasRef}
        className="h-full w-full"
        role="img"
        aria-label="Paper plexus. Color runs from copper at the lower left to pale gold at the upper right."
        onPointerMove={(ev) => setHover(pick(ev))}
        onPointerLeave={() => setHover(null)}
        onClick={(ev) => {
          const id = pick(ev);
          const node = net.nodes.find((n) => n.id === id);
          if (!node?.paper) return;
          onFocus?.(node.id);
          if (node.gap) onHighlight?.(node.cluster);
        }}
      />
      <ul className="sr-only">
        {net.nodes.filter((n) => n.paper).map((n) => (
          <li key={n.id}>
            <button data-testid={showGaps && n.gap ? "gap-node" : "topic-node"} onClick={() => { onFocus?.(n.id); onPick?.(n.id); }}>
              {n.id}, paper{n.cluster ? `, topic cluster ${n.cluster}` : ""}{showGaps && n.gap ? ", research gap" : ""}
            </button>
          </li>
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

function hexAlpha(hex: string, alpha: number) {
  const n = Number.parseInt(hex.slice(1), 16);
  const r = (n >> 16) & 255;
  const g = (n >> 8) & 255;
  const b = n & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
