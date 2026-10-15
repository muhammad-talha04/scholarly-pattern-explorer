"use client";
import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { api } from "@/lib/api/client";
import { lifecycles } from "@/lib/graph";
import { useApi } from "@/lib/useApi";
import { ErrorNote, PageHeader, Spinner } from "@/components/ui";
import { deriveRules } from "./rules";

type Tab = "itemsets" | "rules" | "lifecycles" | "gaps";
export function PatternsPage() {
  const all = useApi(() => api.patterns(), []);
  const gaps = useApi(() => api.patterns({ trend: "gap" }), []);
  const windows = useMemo(() => [...new Set((all.data ?? []).map((p) => p.window_start))].sort(), [all.data]);
  const [win, setWin] = useState<number | null>(null);
  const [tab, setTab] = useState<Tab>("itemsets");
  useEffect(() => { if (win === null && windows.length) setWin(windows[windows.length - 1]); }, [windows, win]);
  const inWin = useMemo(() => (all.data ?? []).filter((p) => p.window_start === win), [all.data, win]);
  const rules = useMemo(() => deriveRules(inWin), [inWin]);
  const life = useMemo(() => lifecycles(all.data ?? []), [all.data]);
  if (all.loading) return <Spinner />;
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
              {r.supports.map((s, i) => <td key={i} className="p-1"><div title={s?.toFixed(3) ?? "absent"} className="mx-auto h-5 w-10 rounded" style={{ background: s == null ? "rgba(255,255,255,.04)" : `rgba(125,211,252,${0.15 + Math.min(1, s * 3)})` }} /></td>)}
              <td className="p-2 text-teal">{r.born}</td><td className="p-2 text-rose">{r.died ?? "alive"}</td></tr>)}</tbody></table>
        )}
        {tab === "gaps" && (gaps.loading ? <Spinner /> :
          <div className="grid gap-3 md:grid-cols-2">{(gaps.data ?? []).map((g) => (
            <div key={g.items[0]} className="rounded-xl border border-gap/30 bg-gap/10 p-4">
              <div className="flex justify-between"><h3 className="font-medium text-gap">{g.items[0]}</h3><span className="chip">score {(g.gap_score ?? g.support).toFixed(2)}</span></div>
              <p className="mt-1 text-sm text-slate-400">Growth {g.growth_rate != null ? `${(g.growth_rate * 100).toFixed(0)}%/yr` : "n/a"} · {g.paper_count ?? "?"} papers · {g.window_start}–{g.window_end}</p>
              {g.top_countries && <p className="mt-1 text-xs text-slate-500">Top countries (fractional): {g.top_countries.join(", ")}</p>}
            </div>))}</div>)}
      </motion.div>
    </div>
  );
}
