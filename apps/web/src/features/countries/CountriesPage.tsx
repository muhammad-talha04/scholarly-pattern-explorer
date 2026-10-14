"use client";
import dynamic from "next/dynamic";
import { useState } from "react";
import { motion } from "framer-motion";
import { api } from "@/lib/api/client";
import type { Counting } from "@/lib/api/types";
import { useApi } from "@/lib/useApi";
import { useMotionPrefs } from "@/components/MotionProvider";
import { ErrorNote, PageHeader, Spinner } from "@/components/ui";
import { CountingToggle } from "./CountingToggle";
import { Globe2D } from "./Globe2D";

const Globe3D = dynamic(() => import("./Globe3D"), { ssr: false, loading: () => <div className="h-full animate-pulse" /> });

export function CountriesPage() {
  const { lowPower } = useMotionPrefs();
  const [counting, setCounting] = useState<Counting>("fractional");
  const [sel, setSel] = useState<string | null>(null);
  const cs = useApi(() => api.countries(counting), [counting]);
  const col = useApi(() => api.collaborations(), []);
  const list = [...(cs.data ?? [])].sort((a, b) => b.papers - a.papers);
  const current = list.find((c) => c.code === sel);
  const partners = (col.data ?? []).filter((c) => c.source === sel || c.target === sel).sort((a, b) => b.papers - a.papers);
  const fmt = (n: number) => (counting === "fractional" ? n.toLocaleString(undefined, { maximumFractionDigits: 1 }) : n.toLocaleString());
  return (
    <div>
      <PageHeader title="Countries" subtitle="Paper counts, growth and collaboration arcs."><CountingToggle value={counting} onChange={setCounting} /></PageHeader>
      {cs.error && <ErrorNote msg={cs.error} />}
      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <div className="glass relative h-[560px] overflow-hidden">
          {cs.loading && !cs.data ? <div className="p-6"><Spinner /></div> : lowPower
            ? <Globe2D countries={list} collabs={col.data ?? []} selected={sel} onSelect={setSel} />
            : <Globe3D countries={list} collabs={col.data ?? []} selected={sel} onSelect={setSel} />}
          <span className="chip absolute bottom-3 left-3">{counting} counting · bars = papers · arcs = co-authorship</span>
        </div>
        <div className="space-y-4">
          {current && (
            <motion.div key={current.code} initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} className="glass p-4">
              <div className="flex items-baseline justify-between"><h2 className="text-lg font-semibold">{current.name}</h2><button className="chip" onClick={() => setSel(null)}>clear</button></div>
              <p className="mt-1 text-sm text-slate-400">{fmt(current.papers)} papers ({counting}) · growth <Growth v={current.growth_pct} /></p>
              <h3 className="mt-3 text-xs uppercase tracking-wide text-slate-400">Top topics</h3>
              <div className="mt-1 flex flex-wrap gap-1.5">{current.top_topics.map((t) => <span key={t} className="chip">{t}</span>)}</div>
              {partners.length > 0 && <><h3 className="mt-3 text-xs uppercase tracking-wide text-slate-400">Top collaborators</h3>
                <ul className="mt-1 text-sm">{partners.slice(0, 5).map((p) => <li key={p.source + p.target} className="flex justify-between"><span>{p.source === sel ? p.target : p.source}</span><span className="text-slate-400">{p.papers}</span></li>)}</ul></>}
            </motion.div>
          )}
          <div className="glass max-h-[440px] overflow-y-auto p-2">
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase text-slate-400"><tr><th className="p-2">Country</th><th className="p-2 text-right">Papers</th><th className="p-2 text-right">Growth</th></tr></thead>
              <tbody>{list.map((c) => (
                <tr key={c.code} onClick={() => setSel(c.code)} className={`cursor-pointer hover:bg-white/5 ${sel === c.code ? "bg-pink-500/10" : ""}`}>
                  <td className="p-2">{c.name}<div className="text-xs text-slate-500">{c.top_topics.slice(0, 2).join(" · ")}</div></td>
                  <td className="p-2 text-right tabular-nums">{fmt(c.papers)}</td>
                  <td className="p-2 text-right"><Growth v={c.growth_pct} /></td>
                </tr>))}</tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
function Growth({ v }: { v: number | null }) {
  if (v == null) return <span className="text-slate-500">n/a</span>;
  return <span className={v >= 0 ? "text-emerald-300" : "text-rose-300"}>{v >= 0 ? "+" : ""}{v.toFixed(1)}%</span>;
}
