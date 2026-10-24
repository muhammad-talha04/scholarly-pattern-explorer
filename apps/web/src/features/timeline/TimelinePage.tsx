"use client";
import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { api } from "@/lib/api/client";
import type { ChartScale } from "@/lib/api/types";
import { seriesFromTopicAggregate } from "@/lib/charts/aggregate";
import { selectBornDied } from "@/lib/graph";
import { useApi } from "@/lib/useApi";
import { EmptyState, ErrorNote, LoadingBlock, PageHeader, Stat } from "@/components/ui";
import { Streamgraph } from "./Streamgraph";
import { VolumeChart } from "./VolumeChart";

const fmtDate = (s: string) => new Date(s).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });

export function TimelinePage({ scale = "sample", initialYear = null }: { scale?: ChartScale; initialYear?: number | null }) {
  const [year, setYear] = useState<number | null>(initialYear);
  const grain = year == null ? "year" : "month";
  const runs = useApi(() => api.runs(), []);
  const pats = useApi(() => api.patterns(), []);
  const pubs = useApi(() => api.publications({ grain, year, scale }), [grain, year, scale]);
  const topics = useApi(() => api.topicVolume({ grain, year, top: 6, scale }), [grain, year, scale]);
  const list = useMemo(() => [...(runs.data ?? [])].sort((a, b) => a.started_at.localeCompare(b.started_at)), [runs.data]);
  const [idx, setIdx] = useState(0);
  useEffect(() => setIdx(Math.max(0, list.length - 1)), [list.length]);
  const series = useMemo(() => (topics.data ? seriesFromTopicAggregate(topics.data) : []), [topics.data]);
  if (runs.loading && !runs.data) return <LoadingBlock label="Loading runs" />;
  if (runs.error) return <ErrorNote msg={runs.error} onRetry={runs.reload} />;
  const cur = list[idx];
  const max = Math.max(...list.map((r) => r.papers_added), 1);
  const cumulative = list.slice(0, idx + 1).reduce((s, r) => s + r.papers_added, 0);
  const runYear = cur ? new Date(cur.started_at).getUTCFullYear() : 0;
  const life = selectBornDied(pats.data ?? [], runYear);
  return (
    <div>
      <PageHeader title="Progress timeline" subtitle="Publication dates of the corpus, then every scheduled incremental run, with the topics moving underneath." />
      <section className="glass mb-4 p-4 sm:p-5" data-testid="publication-section">
        <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="font-display text-2xl text-white">Estimated OpenAlex output</h2>
            <p className="mt-1 text-sm text-mist">
              Papers are sampled evenly each month, so a raw count looks flat. Bars are the estimated total
              {year == null ? " by year" : ` by month in ${year}`}.
              {pubs.data ? ` ${pubs.data.estimated_total == null ? "estimate unavailable" : `${pubs.data.estimated_total.toLocaleString("en-US")} estimated`} · ${pubs.data.sampled.toLocaleString("en-US")} sampled.` : ""}
            </p>
          </div>
          {year != null && (
            <button type="button" className="btn" onClick={() => setYear(null)}>All years</button>
          )}
        </div>
        {pubs.loading && !pubs.data ? <LoadingBlock label="Loading publication totals" /> : pubs.error ? <ErrorNote msg={pubs.error} onRetry={pubs.reload} /> : pubs.data ? (
          <VolumeChart data={pubs.data} onDrill={(y) => setYear(y)} />
        ) : (
          <EmptyState title="Waiting for publication totals" body="GET /aggregates/publications is not on this API yet. The chart appears once that route returns sampled and estimated_total for each year and month. It does not count papers in the browser." />
        )}
      </section>
      {list.length === 0 ? <EmptyState title="No runs yet" body="The timeline fills in after the first ingest. Patterns and the topic stream can still load on their own." /> : <>
        <div className="glass p-4 sm:p-5">
          <h2 className="mb-3 font-display text-2xl text-white">Ingest runs</h2>
          {list.length < 2 ? (
            <p className="max-w-2xl text-sm text-mist">
              One ingest run so far: the initial load of {list[0].papers_added.toLocaleString()} papers on {fmtDate(list[0].started_at)}.
              Each weekly update will add its own bar here, so you can step through how the corpus and its patterns changed.
            </p>
          ) : (<>
          <div className="flex h-44 items-end gap-1" aria-label="Papers added per run">
            {list.map((r, i) => (
              <button key={r.id} onClick={() => setIdx(i)} aria-label={`${fmtDate(r.started_at)}: ${r.papers_added} papers`} title={`${fmtDate(r.started_at)}: ${r.papers_added} papers`} className="group flex h-full min-w-0 flex-1 flex-col justify-end focus:outline-none focus-visible:ring-2 focus-visible:ring-accent">
                <motion.div initial={{ height: 0 }} animate={{ height: `${Math.max(2, (r.papers_added / max) * 100)}%` }} transition={{ delay: Math.min(i, 20) * 0.015 }}
                  className={`w-full rounded-t ${r.status !== "success" ? "bg-down/80" : i === idx ? "bg-gradient-to-t from-accent to-gap" : i < idx ? "bg-accent/50" : "bg-white/15"} group-hover:brightness-125`} />
              </button>
            ))}
          </div>
          <input type="range" aria-label="Run scrubber" min={0} max={list.length - 1} value={idx} onChange={(e) => setIdx(Number(e.target.value))} className="mt-4 w-full accent-accent" />
          <div className="mt-1 flex justify-between text-xs text-mist"><span>{fmtDate(list[0].started_at)}</span><span>{fmtDate(list[list.length - 1].started_at)}</span></div>
          </>)}
        </div>
        {cur && (
          <motion.div key={cur.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <Stat label={`Run #${cur.id}`} value={<span className="text-base">{fmtDate(cur.started_at)}</span>} />
            <Stat label="Status" value={<span className={cur.status === "success" ? "text-up" : "text-down"}>{cur.status}</span>} />
            <Stat label="Papers added" value={cur.papers_added.toLocaleString()} />
            <Stat label="Total so far" value={cumulative.toLocaleString()} />
            <Stat label="Patterns changed" value={cur.patterns_changed} />
          </motion.div>
        )}
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <LifePanel tone="born" title="Patterns born" life={life} />
          <LifePanel tone="died" title="Patterns died" life={life} />
        </div>
        <p className="mt-3 text-xs text-slate-400">Born and died come from /patterns windows. A run only stores how many patterns changed, not which ones.</p>
      </>}
      <section className="glass mt-4 p-4 sm:p-5">
        <h2 className="font-display text-2xl text-white">Topic stream</h2>
        <p className="mb-3 mt-1 text-sm text-mist">
          {year == null ? "Each year is the percent of that period." : `Each month in ${year} is the percent of that period.`} Columns sum to 100% when the period has papers. Select a year on the chart above, or a column here, to open that year.
        </p>
        {topics.loading && !topics.data ? <LoadingBlock label="Loading topic totals" /> : topics.error ? <ErrorNote msg={topics.error} onRetry={topics.reload} /> : topics.data ? (
          <Streamgraph series={series} onSelect={(key) => { if (year == null && /^\d{4}$/.test(key)) setYear(Number(key)); }} />
        ) : (
          <EmptyState title="Waiting for topic totals" body="GET /aggregates/topics is not on this API yet. The stream appears once that route returns precomputed topic totals. It does not download the topic × country × year table and count it here." />
        )}
      </section>
    </div>
  );
}

function LifePanel({ tone, title, life }: { tone: "born" | "died"; title: string; life: ReturnType<typeof selectBornDied> }) {
  const rows = tone === "born" ? life.born : life.died;
  const color = tone === "born" ? "text-up" : "text-down";
  const mark = tone === "born" ? "+" : "−";
  return (
    <div className="glass p-4">
      <h3 className={`text-sm font-semibold ${color}`}>{title}{life.win != null ? ` (window ${life.win})` : ""}</h3>
      {life.note === "fallback" && <p className="mt-1 text-xs text-mist">Window {life.matched} has no changes. Showing the latest window that does.</p>}
      {life.note === "stable" && <p className="mt-2 text-sm text-mist">Every pattern in this snapshot has been here since the first window and is still active. Nothing is born or dying in {life.matched}.</p>}
      {life.note === "no-patterns" && <p className="mt-2 text-sm text-mist">No pattern windows have been published yet.</p>}
      {rows.length > 0 ? (
        <ul className="mt-2 space-y-1 text-sm">
          {rows.slice(0, 10).map((r) => <li key={r.key}>{mark} {r.key}</li>)}
          {rows.length > 10 && <li className="text-mist">and {rows.length - 10} more</li>}
        </ul>
      ) : life.note === "matched" ? <p className="mt-2 text-sm text-mist">None in this window.</p> : null}
    </div>
  );
}
