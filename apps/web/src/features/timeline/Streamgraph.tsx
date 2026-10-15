"use client";
import { useMemo, useState } from "react";
import type { TopicCountryYear } from "@/lib/api/types";
import { streamBands, topicSeries } from "@/lib/series";
import { chartColor, ink, mist } from "@/lib/theme";

export function Streamgraph({ rows }: { rows: TopicCountryYear[] }) {
  const bands = useMemo(() => streamBands(topicSeries(rows, 7, false)), [rows]);
  const [hi, setHi] = useState<number | null>(null);
  if (!bands.length || bands[0].points.length < 2) {
    return <p className="text-sm text-mist">Not enough topic-year rows to draw a stream yet.</p>;
  }
  const years = bands[0].points.map((p) => p.year);
  const flat = bands.flatMap((b) => b.points.flatMap((p) => [p.y0, p.y1]));
  const min = Math.min(...flat), max = Math.max(...flat);
  const W = 760, H = 280, pad = 28;
  const x = (i: number) => pad + (i / (years.length - 1)) * (W - pad * 2);
  const y = (v: number) => H - pad - ((v - min) / (max - min || 1)) * (H - pad * 2);
  const path = (band: typeof bands[number]) => {
    const top = band.points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(p.y1).toFixed(1)}`);
    const bot = [...band.points].reverse().map((p, i) => `L${x(band.points.length - 1 - i).toFixed(1)} ${y(p.y0).toFixed(1)}`);
    return `${top.join(" ")} ${bot.join(" ")} Z`;
  };
  const active = hi ?? years.length - 1;
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="h-64 w-full" role="img" aria-label="Topic volume by year, stacked as a stream">
        {bands.map((b, i) => (
          <path key={b.name} d={path(b)} fill={chartColor(i)} opacity={0.88} stroke={ink} strokeWidth={0.6}>
            <title>{b.name}</title>
          </path>
        ))}
        {years.map((year, i) => (
          <rect key={year} x={x(i) - (x(1) - x(0)) / 2} y={pad / 2} width={x(1) - x(0)} height={H - pad} fill="transparent"
            onMouseEnter={() => setHi(i)} onFocus={() => setHi(i)} />
        ))}
        <line x1={x(active)} x2={x(active)} y1={16} y2={H - 18} stroke="white" strokeOpacity={0.45} />
        {years.map((year, i) => (i % 2 === 0 || i === years.length - 1) && (
          <text key={year} x={x(i)} y={H - 6} textAnchor="middle" fill={mist} fontSize={11}>{year}</text>
        ))}
      </svg>
      <ul className="mt-2 flex flex-wrap gap-2 text-xs text-mist">
        {bands.map((b, i) => <li key={b.name} className="inline-flex items-center gap-1"><span className="inline-block h-2 w-2 rounded-full" style={{ background: chartColor(i) }} />{b.name}</li>)}
      </ul>
      <p className="mt-2 text-xs text-mist">{years[active]} fractional papers: {bands.map((b) => `${b.name} ${(b.points[active].y1 - b.points[active].y0).toFixed(0)}`).join(" · ")}</p>
      <details className="mt-2 text-xs text-mist">
        <summary className="cursor-pointer">Table of the same numbers</summary>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full text-left">
            <thead><tr><th className="p-1">Topic</th>{years.map((y) => <th key={y} className="p-1">{y}</th>)}</tr></thead>
            <tbody>{bands.map((b) => <tr key={b.name}><td className="p-1">{b.name}</td>{b.points.map((p) => <td key={p.year} className="p-1 tabular-nums">{(p.y1 - p.y0).toFixed(0)}</td>)}</tr>)}</tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
