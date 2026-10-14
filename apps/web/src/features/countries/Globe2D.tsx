"use client";
import type { Collaboration, CountryStats } from "@/lib/api/types";
import { CENTROIDS } from "@/lib/geo";
/** Equirectangular SVG fallback: dots sized by papers, arcs for collaborations. */
export function Globe2D({ countries, collabs, selected, onSelect }: { countries: CountryStats[]; collabs: Collaboration[]; selected: string | null; onSelect: (c: string) => void }) {
  const X = (lng: number) => ((lng + 180) / 360) * 800, Y = (lat: number) => ((90 - lat) / 180) * 400;
  const max = Math.max(...countries.map((c) => c.papers), 1);
  return (
    <svg viewBox="0 0 800 400" className="h-full w-full" role="img" aria-label="Country map (2D)">
      <rect width="800" height="400" fill="#0b1230" rx="16" />
      {Array.from({ length: 11 }, (_, i) => <line key={i} x1={i * 80} x2={i * 80} y1={0} y2={400} stroke="#7dd3fc" strokeOpacity={0.06} />)}
      {collabs.map((c, i) => {
        const a = CENTROIDS[c.source], b = CENTROIDS[c.target]; if (!a || !b) return null;
        const x1 = X(a[1]), y1 = Y(a[0]), x2 = X(b[1]), y2 = Y(b[0]);
        return <path key={i} d={`M${x1},${y1} Q${(x1 + x2) / 2},${Math.min(y1, y2) - 60} ${x2},${y2}`} fill="none" stroke="#a78bfa" strokeOpacity={0.5} />;
      })}
      {countries.map((c) => {
        const ll = CENTROIDS[c.code]; if (!ll) return null;
        return <circle key={c.code} cx={X(ll[1])} cy={Y(ll[0])} r={3 + 14 * Math.sqrt(c.papers / max)} fill={selected === c.code ? "#f472b6" : "#38bdf8"} fillOpacity={0.75} className="cursor-pointer" onClick={() => onSelect(c.code)}><title>{c.name}: {c.papers}</title></circle>;
      })}
    </svg>
  );
}
