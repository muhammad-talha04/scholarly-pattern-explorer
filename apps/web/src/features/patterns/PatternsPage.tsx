"use client";
import { useMemo, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { api } from "@/lib/api/client";
import { lifecycles } from "@/lib/graph";
import { useApi } from "@/lib/useApi";
import { ErrorNote, PageHeader, Spinner } from "@/components/ui";
import { chartColor } from "@/lib/theme";
import { deriveRules } from "./rules";
import type { Pattern } from "@/lib/api/types";

type Tab = "itemsets" | "rules" | "lifecycles" | "gaps";
export function PatternsPage({ initial = {} }: { initial?: { all?: Pattern[]; gaps?: Pattern[]; emerging?: Pattern[] } } = {}) {
  const all = useApi(() => api.patterns(), [], initial.all);
  const gaps = useApi(() => api.patterns({ trend: "gap" }), [], initial.gaps);
  const emerging = useApi(() => api.patterns({ trend: "emerging" }), [], initial.emerging);
  const windows = useMemo(() => [...new Set((all.data ?? []).map((p) => p.window_start))].sort(), [all.data]);
  const [pickedWin, setWin] = useState<number | null>(null);
  const win = pickedWin ?? (windows.length ? windows[windows.length - 1] : null);
  const [tab, setTab] = useState<Tab>("itemsets");
  const inWin = useMemo(() => (all.data ?? []).filter((p) => p.window_start === win), [all.data, win]);
  const rules = useMemo(() => deriveRules(inWin), [inWin]);
  const life = useMemo(() => lifecycles(all.data ?? []), [all.data]);
  if (all.loading && !all.data) return <Spinner />;
  if (all.error) return <ErrorNote msg={all.error} />;
  return (
    <div>
      <PageHeader title="Patterns" subtitle="Frequent topic itemsets, derived rules, lifecycles and research gaps.">
        <select aria-label="Window" value={win ?? ""} onChange={(e) => setWin(Number(e.target.value))} className="input">{windows.map((w) => <option key={w} value={w}>Window {w}</option>)}</select>
      </PageHeader>
      <div className="mb-4 flex gap-1 overflow-x-auto">{(["itemsets", "rules", "lifecycles", "gaps"] as Tab[]).map((t) => (
        <button key={t} onClick={() => setTab(t)} className="relative rounded-lg px-4 py-1.5 text-sm capitalize">
          {tab === t && <motion.span layoutId="pat-tab" className="absolute inset-0 rounded-lg bg-white/10" />}<span className="relative">{t}</span>
        </button>))}</div>
      <motion.div key={tab + win} initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="glass overflow-x-auto p-4">
        {tab === "itemsets" && (
          <table className="w-full text-sm"><thead className="text-left text-xs uppercase text-slate-400"><tr><th className="p-2">Itemset</th><th className="p-2">Size</th><th className="p-2 w-1/3">Support</th></tr></thead>
            <tbody>{[...inWin].sort((a, b) => b.support - a.support).map((p) => (
              <tr key={p.items.join()} className="border-t border-white/5"><td className="p-2">{p.items.map((i) => <span key={i} className="chip mr-1">{i}</span>)}</td><td className="p-2">{p.items.length}</td>
                <td className="p-2"><div className="flex items-center gap-2"><div className="h-1.5 flex-1 rounded bg-white/10"><div className="h-full rounded bg-accent" style={{ width: `${Math.min(100, p.support * 250)}%` }} /></div><span className="tabular-nums text-xs">{p.support.toFixed(3)}</span></div></td></tr>))}</tbody></table>
        )}
        {tab === "rules" && (rules.length === 0 ? <p className="text-slate-400">No rules derivable in this window.</p> :
          <table className="w-full text-sm"><thead className="text-left text-xs uppercase text-slate-400"><tr><th className="p-2">Rule</th><th className="p-2">Support</th><th className="p-2">Confidence</th><th className="p-2">Lift</th></tr></thead>
            <tbody>{rules.map((r, i) => <tr key={i} className="border-t border-white/5"><td className="p-2">{r.antecedent.join(" + ")} <span className="text-accent">→</span> {r.consequent.join(", ")}</td><td className="p-2">{r.support.toFixed(3)}</td><td className="p-2">{(r.confidence * 100).toFixed(0)}%</td><td className="p-2">{r.lift?.toFixed(2) ?? "–"}</td></tr>)}</tbody></table>)}
        {tab === "lifecycles" && (
          <table className="text-sm"><thead className="text-xs text-slate-400"><tr><th className="p-2 text-left">Itemset</th>{life.windows.map((w) => <th key={w} className="p-2">{w}</th>)}<th className="p-2">Born</th><th className="p-2">Died</th></tr></thead>
            <tbody>{life.rows.map((r) => <tr key={r.key} className="border-t border-white/5"><td className="p-2 pr-6">{r.key}</td>
              {r.supports.map((s, i) => <td key={i} className="p-1"><div title={s?.toFixed(3) ?? "absent"} className="mx-auto h-5 w-10 rounded" style={{ background: s == null ? "rgba(255,255,255,.04)" : chartColor(4), opacity: s == null ? 1 : 0.35 + Math.min(0.65, s * 2) }} /></td>)}
              <td className="p-2 text-up">{r.born}</td><td className="p-2 text-down">{r.died ?? "alive"}</td></tr>)}</tbody></table>
        )}
        {tab === "gaps" && (gaps.loading && !gaps.data ? <Spinner /> :
          <div className="space-y-6">
            <div className="grid gap-3 md:grid-cols-2">{(gaps.data ?? []).map((g) => (
              <div key={g.items[0]} className="rounded-xl border border-gap/30 bg-gap/10 p-4">
                <div className="flex justify-between gap-2"><Link href={`/?cluster=${encodeURIComponent(g.items[0])}`} className="font-medium text-gap underline-offset-2 hover:underline">{g.items[0]}</Link><span className="chip">score {(g.gap_score ?? g.support).toFixed(2)}</span></div>
                <p className="mt-1 text-sm text-slate-400">Growth {g.growth_rate != null ? `${(g.growth_rate * 100).toFixed(0)}%/yr` : "n/a"} · {g.paper_count ?? "?"} papers · {g.window_start}–{g.window_end}</p>
                {g.top_countries && <p className="mt-1 text-xs text-slate-500">Top countries (fractional): {g.top_countries.join(", ")}</p>}
              </div>))}</div>
            <div>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-widest text-mist">Emerging topics</h3>
              {emerging.loading && !emerging.data ? <Spinner /> : (
                <ul className="grid gap-2 md:grid-cols-2">
                  {(emerging.data ?? []).map((g) => (
                    <li key={g.items[0]}><Link href={`/?cluster=${encodeURIComponent(g.items[0])}`} className="glass block px-3 py-2 text-sm text-accent hover:underline">{g.items[0]}</Link></li>
                  ))}
                </ul>
              )}
            </div>
          </div>)}
      </motion.div>
    </div>
  );
}
