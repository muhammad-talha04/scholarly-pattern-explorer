"use client";
import { useState } from "react";
import type { PaperSummary } from "@/lib/api/types";
import { accent, mist, violet } from "@/lib/palette";

/** Related papers as a small radial map. Layout is computed here; no extra service. */
export function CitationMap({ center, related, onOpen }: { center: string; related: PaperSummary[]; onOpen: (id: string) => void }) {
  const [hover, setHover] = useState<string | null>(null);
  if (related.length === 0) {
    return <p className="text-sm text-mist">No related papers in this snapshot yet.</p>;
  }
  const W = 360, H = 230, cx = W / 2, cy = H / 2 + 6;
  const nodes = related.map((p, i) => {
    const a = (Math.PI * 2 * i) / related.length - Math.PI / 2;
    const rx = Math.min(150, 70 + related.length * 10);
    return { ...p, x: cx + Math.cos(a) * rx, y: cy + Math.sin(a) * 78 };
  });
  const tip = nodes.find((n) => n.id === hover);
  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-52 w-full" role="img" aria-label="Related papers around this one">
        {nodes.map((n) => <line key={n.id} x1={cx} y1={cy} x2={n.x} y2={n.y} stroke={accent} strokeOpacity={0.45} />)}
        <circle cx={cx} cy={cy} r={16} fill={violet} />
        <text x={cx} y={cy + 32} textAnchor="middle" fill={mist} fontSize={10}>this paper</text>
        {nodes.map((n) => (
          <g key={n.id} className="cursor-pointer" onMouseEnter={() => setHover(n.id)} onMouseLeave={() => setHover((h) => (h === n.id ? null : h))} onClick={() => onOpen(n.id)}>
            <circle cx={n.x} cy={n.y} r={hover === n.id ? 11 : 8} fill={accent} />
            <title>{n.title}</title>
          </g>
        ))}
      </svg>
      <ul className="sr-only">
        {related.map((p) => <li key={p.id}><button onClick={() => onOpen(p.id)}>{p.title}</button></li>)}
      </ul>
      {tip && (
        <div className="glass absolute bottom-1 left-1 right-1 px-2 py-1.5 text-xs" role="tooltip">
          <p className="line-clamp-2 text-white">{tip.title}</p>
          <p className="text-mist">{tip.year ?? "n.d."} · {tip.cited_by} citations</p>
        </div>
      )}
      <p className="sr-only">{center}</p>
    </div>
  );
}
