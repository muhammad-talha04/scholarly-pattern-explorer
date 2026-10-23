"use client";
import type { CountryChart as CountryChartData, Counting } from "@/lib/api/types";
import { chartColor, otherColor } from "@/lib/theme";

function fmt(n: number, counting: Counting) {
  return n.toLocaleString("en-US", { maximumFractionDigits: counting === "full" ? 0 : 1 });
}

/** Horizontal bars for the precomputed top-N, plus one Other bar for the tail. */
export function CountryChart({ data }: { data: CountryChartData }) {
  const rows = [
    ...data.items.map((c) => ({ key: c.code, label: c.name, papers: c.papers, other: false })),
    ...(data.other ? [{ key: "other", label: "Other", papers: data.other.papers, other: true }] : []),
  ];
  const max = Math.max(...rows.map((r) => r.papers), 1);
  if (!rows.length) {
    return <p className="text-sm text-mist">No country totals in this aggregate yet.</p>;
  }
  return (
    <div data-testid="country-chart">
      <ol className="space-y-1.5" aria-label="Top countries by papers">
        {rows.map((r) => (
          <li key={r.key} data-testid={r.other ? "country-other" : `country-bar-${r.key}`} className="grid grid-cols-[9.5rem_minmax(0,1fr)_4.75rem] items-center gap-2 sm:grid-cols-[11rem_minmax(0,1fr)_5.5rem]">
            <span className="truncate text-sm text-white" title={r.other && data.other ? `${data.other.countries} countries` : r.label}>
              {r.label}
              {r.other && data.other ? <span className="ml-1 text-xs text-mist">{data.other.countries}</span> : null}
            </span>
            <span className="block h-3 overflow-hidden rounded-full bg-white/5">
              <span className="block h-full rounded-full" style={{ width: `${Math.max(2, (r.papers / max) * 100)}%`, background: r.other ? otherColor : chartColor(1) }} />
            </span>
            <span className="text-right text-xs tabular-nums text-mist">{fmt(r.papers, data.counting)}</span>
          </li>
        ))}
      </ol>
      <p className="mt-3 text-xs text-mist">
        Top {data.items.length}
        {data.other ? ` plus Other (${data.other.countries} countries)` : ""}. {fmt(data.total, data.counting)} papers
        {data.year != null ? ` in ${data.year}` : ""}.
      </p>
    </div>
  );
}
