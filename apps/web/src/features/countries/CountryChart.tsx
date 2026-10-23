"use client";
import type { CountryChart as CountryChartData } from "@/lib/api/types";
import { chartColor, otherColor } from "@/lib/theme";

/** Horizontal bars for the precomputed top-N, plus one Other bar. Width and labels are the share of this period. */
export function CountryChart({ data }: { data: CountryChartData }) {
  const rows = [
    ...data.items.map((c) => ({ key: c.code, label: c.name, share: c.share, other: false })),
    ...(data.other ? [{ key: "other", label: "Other", share: data.other.share, other: true }] : []),
  ];
  const max = Math.max(...rows.map((r) => r.share), 1);
  if (!rows.length) {
    return <p className="text-sm text-mist">No country totals in this aggregate yet.</p>;
  }
  return (
    <div data-testid="country-chart">
      <div className="mb-1 grid grid-cols-[9.5rem_minmax(0,1fr)_4.75rem] text-[11px] text-mist sm:grid-cols-[11rem_minmax(0,1fr)_5.5rem]">
        <span />
        <span className="col-span-2 text-right">Percent of this period</span>
      </div>
      <ol className="space-y-1.5" aria-label="Share of papers in this period">
        {rows.map((r) => (
          <li key={r.key} data-testid={r.other ? "country-other" : `country-bar-${r.key}`} className="grid grid-cols-[9.5rem_minmax(0,1fr)_4.75rem] items-center gap-2 sm:grid-cols-[11rem_minmax(0,1fr)_5.5rem]">
            <span className="truncate text-sm text-white" title={r.other && data.other ? `${data.other.countries} countries` : r.label}>
              {r.label}
              {r.other && data.other ? <span className="ml-1 text-xs text-mist">{data.other.countries}</span> : null}
            </span>
            <span className="block h-3 overflow-hidden rounded-full bg-white/5">
              <span className="block h-full rounded-full" style={{ width: `${Math.max(2, (r.share / max) * 100)}%`, background: r.other ? otherColor : chartColor(1) }} />
            </span>
            <span className="text-right text-xs tabular-nums text-mist">{r.share.toFixed(1)}%</span>
          </li>
        ))}
      </ol>
      <p className="mt-3 text-xs text-mist">
        Top {data.items.length}
        {data.other ? ` plus Other (${data.other.countries} countries)` : ""}
        {data.year != null ? ` in ${data.year}` : ""}.
      </p>
    </div>
  );
}
