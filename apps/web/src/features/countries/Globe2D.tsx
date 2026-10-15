"use client";
import { useMemo, useState } from "react";
import type { Collaboration, CountryStats } from "@/lib/api/types";
import { CENTROIDS } from "@/lib/geo";
import { bordersPath } from "@/lib/world";

/** Equirectangular fallback: country outlines, dots sized by papers, arcs for collaborations. */
export function Globe2D({ countries, collabs, selected, onSelect }: { countries: CountryStats[]; collabs: Collaboration[]; selected: string | null; onSelect: (c: string) => void }) {
  const X = (lng: number) => ((lng + 180) / 360) * 800, Y = (lat: number) => ((90 - lat) / 180) * 400;
  const max = Math.max(...countries.map((c) => c.papers), 1);
  const outline = useMemo(() => bordersPath(800, 400), []);
  const [hover, setHover] = useState<string | null>(null);
  const tip = countries.find((c) => c.code === (hover ?? selected));
  return (
    <div className="relative h-full w-full">
      <svg viewBox="0 0 800 400" className="h-full w-full" role="img" aria-label="Country map, flat drawing">
        <rect width="800" height="400" fill="#10182e" />
        <path d={outline} fill="none" stroke="#9bd7ff" strokeOpacity={0.55} strokeWidth={0.7} />
        {collabs.map((c, i) => {
          const a = CENTROIDS[c.source], b = CENTROIDS[c.target]; if (!a || !b) return null;
          const x1 = X(a[1]), y1 = Y(a[0]), x2 = X(b[1]), y2 = Y(b[0]);
          const hot = selected && (c.source === selected || c.target === selected);
          return <path key={i} d={`M${x1},${y1} Q${(x1 + x2) / 2},${Math.min(y1, y2) - 50} ${x2},${y2}`} fill="none" stroke={hot ? "#f9a8d4" : "#c4b5fd"} strokeOpacity={selected && !hot ? 0.15 : 0.7} />;
        })}
        {countries.map((c) => {
          const ll = CENTROIDS[c.code]; if (!ll) return null;
          return (
            <circle key={c.code} cx={X(ll[1])} cy={Y(ll[0])} r={3 + 14 * Math.sqrt(c.papers / max)} fill={selected === c.code ? "#f9a8d4" : "#38bdf8"} fillOpacity={0.8}
              className="cursor-pointer" onMouseEnter={() => setHover(c.code)} onMouseLeave={() => setHover((h) => (h === c.code ? null : h))} onClick={() => onSelect(c.code)}>
              <title>{c.name}: {c.papers}</title>
            </circle>
          );
        })}
      </svg>
      {tip && <div className="glass absolute left-3 top-3 px-2 py-1 text-xs text-white" role="tooltip">{tip.name} · {tip.papers.toLocaleString(undefined, { maximumFractionDigits: 1 })} papers</div>}
    </div>
  );
}
