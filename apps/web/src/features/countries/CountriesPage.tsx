"use client";
import dynamic from "next/dynamic";
import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { api, prefersFixtures } from "@/lib/api/client";
import type { Counting, CountryStats } from "@/lib/api/types";
import { papersByCountryYear, yearRange } from "@/lib/series";
import { useApi } from "@/lib/useApi";
import { useMotionPrefs } from "@/components/MotionProvider";
import { EmptyState, ErrorNote, LoadingBlock, PageHeader } from "@/components/ui";
import { CountingToggle } from "./CountingToggle";
import { Globe2D } from "./Globe2D";

const Globe3D = dynamic(() => import("./Globe3D"), { ssr: false, loading: () => <LoadingBlock label="Raising the globe" /> });

export function CountriesPage() {
  const { lowPower } = useMotionPrefs();
  const [counting, setCounting] = useState<Counting>("fractional");
  const [sel, setSel] = useState<string | null>(null);
  const [year, setYear] = useState<number | "all">("all");
  const cs = useApi(() => api.countries(counting), [counting]);
  const col = useApi(() => api.collaborations(counting), [counting]);
  const tcy = useApi(() => api.topicCountryYears({ limit: 5000 }), []);
  const yearlyReady = tcy.source === "live" || prefersFixtures();
  const range = yearlyReady ? yearRange(tcy.data ?? []) : null;
  const list = useMemo(() => {
    const base = [...(cs.data ?? [])].sort((a, b) => b.papers - a.papers);
    if (year === "all" || !yearlyReady || !tcy.data) return base;
    const by = papersByCountryYear(tcy.data, year, counting);
    return base.map((c) => ({ ...c, papers: by.get(c.code) ?? 0 })).sort((a, b) => b.papers - a.papers);
  }, [cs.data, tcy.data, year, counting, yearlyReady]);
  const current = list.find((c) => c.code === sel);
  const partners = (col.data ?? []).filter((c) => c.source === sel || c.target === sel).sort((a, b) => b.papers - a.papers);
  const fmt = (n: number) => (counting === "full" ? n.toLocaleString() : n.toLocaleString(undefined, { maximumFractionDigits: 1 }));
  return (
    <div>
      <PageHeader title="Countries" subtitle="Paper counts, growth and collaboration arcs. Drag the globe, or pick a row.">
        <CountingToggle value={counting} onChange={setCounting} />
      </PageHeader>
      {cs.error && <ErrorNote msg={cs.error} onRetry={cs.reload} />}
      {range && (
        <div className="glass mb-4 flex flex-wrap items-center gap-4 px-4 py-3">
          <label className="flex items-center gap-2 text-sm text-mist">
            <input type="checkbox" checked={year === "all"} onChange={(e) => setYear(e.target.checked ? "all" : range[1])} />
            All years
          </label>
          <label className="flex min-w-[12rem] flex-1 items-center gap-3 text-sm text-mist">
            <span className="shrink-0">{year === "all" ? "Every year" : year}</span>
            <input type="range" aria-label="Year" min={range[0]} max={range[1]} disabled={year === "all"} value={year === "all" ? range[1] : year}
              onChange={(e) => setYear(Number(e.target.value))} className="w-full accent-accent disabled:opacity-40" />
          </label>
        </div>
      )}
      {!yearlyReady && tcy.source === "mock" && !prefersFixtures() && (
        <p className="mb-3 text-xs text-amber">The topic × country × year table is not on this API yet, so the year slider stays off. Country bars use the live /countries route.</p>
      )}
      <div className="grid gap-4 lg:grid-cols-[1fr_340px]">
        <div className="glass relative h-[420px] overflow-hidden sm:h-[560px]">
          {cs.loading && !cs.data ? <LoadingBlock label="Raising the globe" /> : list.length === 0 ? (
            <div className="flex h-full items-center justify-center p-6"><EmptyState title="No country snapshot yet" body="Bars and arcs appear when /countries returns rows. Talha's country aggregate is what fills this view." /></div>
          ) : lowPower ? <Globe2D countries={list} collabs={col.data ?? []} selected={sel} onSelect={setSel} />
            : <Globe3D countries={list} collabs={col.data ?? []} selected={sel} onSelect={setSel} />}
          <span className="chip pointer-events-none absolute bottom-3 left-3 max-w-[90%]">{counting} counting · bars = papers{year !== "all" ? ` in ${year}` : ""} · arcs = co-authorship</span>
        </div>
        <div className="space-y-4">
          {current && (
            <motion.div key={current.code} initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} className="glass p-4">
              <div className="flex items-baseline justify-between"><h2 className="text-lg font-semibold text-white">{current.name}</h2><button className="chip hover:text-white" onClick={() => setSel(null)}>clear</button></div>
              <p className="mt-1 text-sm text-mist">{fmt(current.papers)} papers ({counting}{year !== "all" ? `, ${year}` : ""}) · growth <Growth v={current.growth_pct} /></p>
              <h3 className="mt-3 text-xs uppercase tracking-wide text-mist">Top topics</h3>
              <div className="mt-1 flex flex-wrap gap-1.5">{current.top_topics.map((t) => <span key={t} className="chip">{t}</span>)}</div>
              {partners.length > 0 && <><h3 className="mt-3 text-xs uppercase tracking-wide text-mist">Top collaborators</h3>
                <ul className="mt-1 text-sm">{partners.slice(0, 5).map((p) => <li key={p.source + p.target} className="flex justify-between"><span>{p.source === sel ? p.target : p.source}</span><span className="text-mist">{fmt(p.papers)}</span></li>)}</ul></>}
            </motion.div>
          )}
          <CountryTable list={list} sel={sel} onSelect={setSel} fmt={fmt} />
        </div>
      </div>
    </div>
  );
}

function CountryTable({ list, sel, onSelect, fmt }: { list: CountryStats[]; sel: string | null; onSelect: (c: string) => void; fmt: (n: number) => string }) {
  return (
    <div className="glass max-h-[440px] overflow-auto p-2">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-ink/90 text-left text-xs uppercase text-mist"><tr><th className="p-2">Country</th><th className="p-2 text-right">Papers</th><th className="p-2 text-right">Growth</th></tr></thead>
        <tbody>{list.map((c) => (
          <tr key={c.code} className={sel === c.code ? "bg-gap/10" : ""}>
            <td className="p-0"><button className="w-full px-2 py-2 text-left hover:bg-white/5 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent" onClick={() => onSelect(c.code)} aria-pressed={sel === c.code}>{c.name}<div className="text-xs text-slate-400">{c.top_topics.slice(0, 2).join(" · ")}</div></button></td>
            <td className="p-2 text-right tabular-nums">{fmt(c.papers)}</td>
            <td className="p-2 text-right"><Growth v={c.growth_pct} /></td>
          </tr>))}</tbody>
      </table>
    </div>
  );
}

function Growth({ v }: { v: number | null }) {
  if (v == null) return <span className="text-slate-400">n/a</span>;
  return <span className={v >= 0 ? "text-teal" : "text-coral"}>{v >= 0 ? "+" : ""}{v.toFixed(1)}%</span>;
}
