"use client";
import { useMemo, useState } from "react";
import type { TopicSeries } from "@/lib/series";
import { tickLabel, visibleTickIndexes } from "@/lib/charts/axis";
import { chartColor, ink, mist } from "@/lib/theme";

interface StackPoint { key: string; y0: number; y1: number; share: number }
interface StackBand { name: string; points: StackPoint[] }

/** Baseline stack of period shares. 0 is the axis; 100 is the top of a full period. */
function shareStack(series: TopicSeries[]): StackBand[] {
  if (!series.length) return [];
  const keys = series[0].keys?.length ? series[0].keys : series[0].years.map(String);
  const running = keys.map(() => 0);
  return series.map((s) => ({
    name: s.name,
    points: keys.map((key, i) => {
      const share = s.values[i] ?? 0;
      const y0 = running[i];
      running[i] += share;
      return { key, y0, y1: running[i], share };
    }),
  }));
}

export function Streamgraph({ series, onSelect }: { series: TopicSeries[]; onSelect?: (key: string) => void }) {
  const bands = useMemo(() => shareStack(series), [series]);
  const [hi, setHi] = useState<number | null>(null);
  if (!bands.length || bands[0].points.length < 2) {
    return <p className="text-sm text-mist">Not enough topic totals to draw a stream yet.</p>;
  }
  const points = bands[0].points;
  const W = 760, H = 280, padL = 72, padR = 16, padT = 16, padB = 36;
  const x = (i: number) => padL + (points.length === 1 ? 0 : (i / (points.length - 1)) * (W - padL - padR));
  const y = (v: number) => H - padB - (v / 100) * (H - padT - padB);
  const path = (band: StackBand) => {
    const top = band.points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(p.y1).toFixed(1)}`);
    const bot = [...band.points].reverse().map((p, i) => `L${x(band.points.length - 1 - i).toFixed(1)} ${y(p.y0).toFixed(1)}`);
    return `${top.join(" ")} ${bot.join(" ")} Z`;
  };
  const labels = points.map((p) => tickLabel(p.key));
  const xs = points.map((_, i) => x(i));
  const shown = new Set(visibleTickIndexes(labels, xs));
  const active = hi ?? points.length - 1;
  const slot = points.length > 1 ? x(1) - x(0) : W;
  const emptyColumn = (i: number) => bands.every((b) => b.points[i].share === 0);
  return (
    <div data-testid="topic-stream">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-64 w-full" role="img" aria-label="Topic share of each period, stacked from 0 to 100 percent">
        <text transform={`rotate(-90 14 ${H / 2})`} x={14} y={H / 2} textAnchor="middle" fill={mist} fontSize={11}>Percent of that period</text>
        {[0, 50, 100].map((t) => (
          <g key={t}>
            <line x1={padL} x2={W - padR} y1={y(t)} y2={y(t)} stroke="white" strokeOpacity={0.08} />
            <text x={padL - 8} y={y(t) + 4} textAnchor="end" fill={mist} fontSize={11}>{t}%</text>
          </g>
        ))}
        {bands.map((b, i) => (
          <path key={b.name} d={path(b)} fill={chartColor(i)} opacity={0.88} stroke={ink} strokeWidth={0.6}>
            <title>{b.name}</title>
          </path>
        ))}
        {points.map((p, i) => (
          <rect key={p.key} x={x(i) - slot / 2} y={padT / 2} width={slot} height={H - padB} fill="transparent"
            role={onSelect ? "button" : undefined}
            tabIndex={onSelect ? 0 : undefined}
            aria-label={onSelect ? `${tickLabel(p.key)}: show this period` : undefined}
            onMouseEnter={() => setHi(i)} onMouseLeave={() => setHi((h) => (h === i ? null : h))} onFocus={() => setHi(i)}
            onClick={() => onSelect?.(p.key)}
            onKeyDown={(e) => { if (onSelect && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); onSelect(p.key); } }} />
        ))}
        <line x1={x(active)} x2={x(active)} y1={16} y2={H - padB + 4} stroke="white" strokeOpacity={0.45} />
        {points.map((p, i) => shown.has(i) && (
          <text key={p.key} x={x(i)} y={H - 10} textAnchor="middle" fill={mist} fontSize={11}>{tickLabel(p.key)}</text>
        ))}
      </svg>
      <ul className="mt-2 flex flex-wrap gap-2 text-xs text-mist">
        {bands.map((b, i) => <li key={b.name} className="inline-flex items-center gap-1"><span className="inline-block h-2 w-2 rounded-full" style={{ background: chartColor(i) }} />{b.name}</li>)}
      </ul>
      <p className="mt-2 text-xs text-mist">
        {tickLabel(points[active].key)}: {bands.map((b) => `${b.name} ${b.points[active].share.toFixed(1)}%`).join(" · ")}
      </p>
      {points.some((_, i) => emptyColumn(i)) && (
        <p className="mt-1 text-xs text-mist">Months with no papers stay at 0% on the axis instead of being dropped.</p>
      )}
      <details className="mt-2 text-xs text-mist">
        <summary className="cursor-pointer">Table of the same numbers</summary>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full text-left">
            <thead><tr><th className="p-1">Topic</th>{points.map((p) => <th key={p.key} className="p-1">{tickLabel(p.key)}</th>)}</tr></thead>
            <tbody>{bands.map((b) => <tr key={b.name}><td className="p-1">{b.name}</td>{b.points.map((p) => <td key={p.key} className="p-1 tabular-nums">{p.share === 0 ? "—" : `${p.share.toFixed(1)}%`}</td>)}</tr>)}</tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
