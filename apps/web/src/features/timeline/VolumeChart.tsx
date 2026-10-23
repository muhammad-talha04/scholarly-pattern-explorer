"use client";
import { useState } from "react";
import type { PublicationAggregate } from "@/lib/api/types";
import { compactCount, tickLabel, visibleTickIndexes } from "@/lib/charts/axis";
import { accent, ink, mist } from "@/lib/theme";

const W = 760, H = 280, padL = 78, padR = 16, padT = 16, padB = 36;

function fmt(n: number) {
  return n.toLocaleString("en-US");
}

export function VolumeChart({ data, onDrill }: { data: PublicationAggregate; onDrill?: (year: number) => void }) {
  const buckets = data.buckets;
  const [hi, setHi] = useState<number | null>(null);
  if (buckets.length === 0) {
    return <p className="text-sm text-mist">No publication totals in this aggregate yet.</p>;
  }
  const n = buckets.length;
  const inner = W - padL - padR;
  const slot = inner / n;
  const barW = Math.max(2, slot * 0.62);
  const max = Math.max(...buckets.map((b) => b.estimated_total), 1);
  const x = (i: number) => padL + slot * i + slot / 2;
  const y = (v: number) => H - padB - (v / max) * (H - padT - padB);
  const base = H - padB;
  const labels = buckets.map((b) => tickLabel(b.key));
  const xs = buckets.map((_, i) => x(i));
  const shown = new Set(visibleTickIndexes(labels, xs));
  const active = hi ?? n - 1;
  const cur = buckets[active];
  const grain = data.grain;
  const ticks = [0, max / 2, max];
  const tip = (label: string, estimated: number, sampled: number) =>
    `${label}: Estimated OpenAlex output ${fmt(estimated)}. Sampled ${fmt(sampled)}.`;
  return (
    <div data-testid="publication-chart">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-64 w-full" role="img" aria-label={grain === "month" ? `Estimated OpenAlex output by month in ${data.year}` : "Estimated OpenAlex output by year"}>
        <text transform={`rotate(-90 16 ${H / 2})`} x={16} y={H / 2} textAnchor="middle" fill={mist} fontSize={11}>Estimated OpenAlex output</text>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={padL} x2={W - padR} y1={y(t)} y2={y(t)} stroke="white" strokeOpacity={0.08} />
            <text x={padL - 8} y={y(t) + 4} textAnchor="end" fill={mist} fontSize={11}>{compactCount(t)}</text>
          </g>
        ))}
        {buckets.map((b, i) => {
          const h = Math.max(0, base - y(b.estimated_total));
          const zero = b.estimated_total === 0 && b.sampled === 0;
          const label = tickLabel(b.key);
          const year = Number(b.key.slice(0, 4));
          const drill = grain === "year" && onDrill;
          return (
            <g key={b.key} data-testid={zero ? "empty-month" : `bucket-${b.key}`}
              onMouseEnter={() => setHi(i)} onMouseLeave={() => setHi(null)}
              onFocus={() => setHi(i)} onBlur={() => setHi(null)}>
              {drill ? (
                <rect x={x(i) - slot / 2} y={padT} width={slot} height={base - padT} fill="transparent" role="button" tabIndex={0}
                  aria-label={`${b.key}: Estimated OpenAlex output ${fmt(b.estimated_total)}. Sampled ${fmt(b.sampled)}. Show months.`}
                  className="cursor-pointer focus:outline-none"
                  onClick={() => onDrill(year)}
                  onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onDrill(year); } }} />
              ) : (
                <rect x={x(i) - slot / 2} y={padT} width={slot} height={base - padT} fill="transparent" />
              )}
              {zero ? (
                <rect x={x(i) - barW / 2} y={base - 3} width={barW} height={3} rx={1.5} fill={mist} opacity={0.55} />
              ) : (
                <rect x={x(i) - barW / 2} y={y(b.estimated_total)} width={barW} height={h} rx={3}
                  fill={i === active ? accent : "#C96A22"} opacity={i === active ? 1 : 0.82} />
              )}
              <title>{tip(label, b.estimated_total, b.sampled)}</title>
              {shown.has(i) && (
                <text x={x(i)} y={H - 12} textAnchor="middle" fill={mist} fontSize={11}>{label}</text>
              )}
            </g>
          );
        })}
        <line x1={padL} x2={W - padR} y1={base} y2={base} stroke={ink} strokeOpacity={0.2} />
      </svg>
      <p className="mt-2 text-xs text-mist" data-testid="publication-caption">
        {grain === "month" ? `${tickLabel(cur.key)} ${data.year}` : cur.key}
        {` · Estimated OpenAlex output ${fmt(cur.estimated_total)} · sampled ${fmt(cur.sampled)}`}
        {grain === "year" ? " · select a year for months" : ""}
      </p>
      {buckets.some((b) => b.sampled === 0 && b.estimated_total === 0) && (
        <p className="mt-1 text-xs text-mist">Empty months stay on the axis, so a gap is a gap and not a skipped label.</p>
      )}
      <details className="mt-2 text-xs text-mist">
        <summary className="cursor-pointer">Table of the same numbers</summary>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full text-left">
            <thead><tr><th className="p-1" />{buckets.map((b) => <th key={b.key} className="p-1">{tickLabel(b.key)}</th>)}</tr></thead>
            <tbody>
              <tr>
                <th className="p-1 text-left font-medium">Estimated OpenAlex output</th>
                {buckets.map((b) => <td key={b.key} className="p-1 tabular-nums">{b.estimated_total === 0 && b.sampled === 0 ? "—" : fmt(b.estimated_total)}</td>)}
              </tr>
              <tr>
                <th className="p-1 text-left font-medium">Sampled</th>
                {buckets.map((b) => <td key={b.key} className="p-1 tabular-nums">{b.estimated_total === 0 && b.sampled === 0 ? "—" : fmt(b.sampled)}</td>)}
              </tr>
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
