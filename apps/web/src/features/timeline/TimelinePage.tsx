"use client";
import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { api } from "@/lib/api/client";
import { lifecycles } from "@/lib/graph";
import { useApi } from "@/lib/useApi";
import { ErrorNote, PageHeader, Spinner, Stat } from "@/components/ui";

const fmtDate = (s: string) => new Date(s).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });

export function TimelinePage() {
  const runs = useApi(() => api.runs(), []);
  const pats = useApi(() => api.patterns(), []);
  const list = useMemo(() => [...(runs.data ?? [])].sort((a, b) => a.started_at.localeCompare(b.started_at)), [runs.data]);
  const [idx, setIdx] = useState(0);
  useEffect(() => setIdx(Math.max(0, list.length - 1)), [list.length]);
  const life = useMemo(() => lifecycles(pats.data ?? []), [pats.data]);
  if (runs.loading) return <Spinner />;
  if (runs.error) return <ErrorNote msg={runs.error} />;
  const cur = list[idx], max = Math.max(...list.map((r) => r.papers_added), 1);
  const cumulative = list.slice(0, idx + 1).reduce((s, r) => s + r.papers_added, 0);
  const year = cur ? new Date(cur.started_at).getUTCFullYear() : 0;
  const win = [...life.windows].reverse().find((w) => w <= year);
  const born = life.rows.filter((r) => r.born === win && win !== life.windows[0]);
  const died = life.rows.filter((r) => r.died === win);
  return (
    <div>
      <PageHeader title="Progress timeline" subtitle="Every scheduled incremental run (1st and 15th of each month)." />
      {list.length === 0 ? <p className="text-slate-400">No runs yet.</p> : <>
        <div className="glass p-5">
          <div className="flex h-44 items-end gap-1" aria-label="Papers added per run">
            {list.map((r, i) => (
              <button key={r.id} onClick={() => setIdx(i)} title={`${fmtDate(r.started_at)}: ${r.papers_added} papers`} className="group flex h-full flex-1 flex-col justify-end">
                <motion.div initial={{ height: 0 }} animate={{ height: `${Math.max(2, (r.papers_added / max) * 100)}%` }} transition={{ delay: i * 0.02 }}
                  className={`w-full rounded-t ${r.status !== "success" ? "bg-rose-400/70" : i === idx ? "bg-gradient-to-t from-sky-500 to-pink-400" : i < idx ? "bg-sky-400/50" : "bg-white/15"} group-hover:brightness-125`} />
              </button>
            ))}
          </div>
          <input type="range" aria-label="Run scrubber" min={0} max={list.length - 1} value={idx} onChange={(e) => setIdx(Number(e.target.value))} className="mt-4 w-full accent-sky-400" />
          <div className="mt-1 flex justify-between text-xs text-slate-500"><span>{fmtDate(list[0].started_at)}</span><span>{fmtDate(list[list.length - 1].started_at)}</span></div>
        </div>
        {cur && (
          <motion.div key={cur.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <Stat label={`Run #${cur.id}`} value={<span className="text-base">{fmtDate(cur.started_at)}</span>} />
            <Stat label="Status" value={<span className={cur.status === "success" ? "text-emerald-300" : "text-rose-300"}>{cur.status}</span>} />
            <Stat label="Papers added" value={cur.papers_added.toLocaleString()} />
            <Stat label="Total so far" value={cumulative.toLocaleString()} />
            <Stat label="Patterns changed" value={cur.patterns_changed} />
          </motion.div>
        )}
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <div className="glass p-4"><h3 className="text-sm font-semibold text-emerald-300">Patterns born {win ? `(window ${win})` : ""}</h3>
            <ul className="mt-2 space-y-1 text-sm">{born.length ? born.map((r) => <li key={r.key}>+ {r.key}</li>) : <li className="text-slate-500">None in this window.</li>}</ul></div>
          <div className="glass p-4"><h3 className="text-sm font-semibold text-rose-300">Patterns died {win ? `(window ${win})` : ""}</h3>
            <ul className="mt-2 space-y-1 text-sm">{died.length ? died.map((r) => <li key={r.key}>− {r.key}</li>) : <li className="text-slate-500">None in this window.</li>}</ul></div>
        </div>
        <p className="mt-3 text-xs text-slate-500">Born/died is derived from /patterns snapshots by window; Run only exposes patterns_changed.</p>
      </>}
    </div>
  );
}
