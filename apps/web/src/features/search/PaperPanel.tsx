"use client";
import { AnimatePresence, motion } from "framer-motion";
import { api } from "@/lib/api/client";
import { useApi } from "@/lib/useApi";
import { ErrorNote, Spinner } from "@/components/ui";
import { AskChat } from "./AskChat";

export function PaperPanel({ id, onClose, onOpen }: { id: string | null; onClose: () => void; onOpen: (id: string) => void }) {
  return (
    <AnimatePresence>
      {id && (
        <motion.aside key="panel" initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ type: "spring", damping: 28, stiffness: 240 }}
          className="fixed bottom-0 right-0 top-14 z-30 w-full max-w-xl overflow-y-auto border-l border-white/10 bg-ink/90 p-6 backdrop-blur-2xl" aria-label="Paper details">
          <button onClick={onClose} className="chip float-right hover:text-white" aria-label="Close panel">✕ Close</button>
          <PaperBody id={id} onOpen={onOpen} />
        </motion.aside>
      )}
    </AnimatePresence>
  );
}

function PaperBody({ id, onOpen }: { id: string; onOpen: (id: string) => void }) {
  const p = useApi(() => api.paper(id), [id]);
  const rel = useApi(() => api.related(id), [id]);
  if (p.loading) return <Spinner />;
  if (p.error || !p.data) return <ErrorNote msg={p.error ?? "not found"} />;
  const d = p.data, link = d.original_url ?? d.openalex_url;
  return (
    <div className="space-y-6">
      <div>
        <h2 className="pr-16 text-xl font-semibold leading-snug">{d.title}</h2>
        <p className="mt-1 text-sm text-slate-400">{d.authors.join(", ")} · {d.year ?? "n.d."} · {d.cited_by} citations</p>
        <div className="mt-2 flex flex-wrap gap-1.5">{d.topics.map((t) => <span key={t} className="chip">{t}</span>)}{d.countries.map((c) => <span key={c} className="chip text-sky-300">{c}</span>)}</div>
      </div>
      {link && (
        <a href={link} target="_blank" rel="noopener noreferrer" className="flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-sky-500 to-violet-500 px-4 py-3 font-semibold text-white shadow-lg shadow-sky-500/20 transition hover:brightness-110">
          Read original paper ↗
        </a>
      )}
      <section><h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-400">Summary</h3><p className="text-sm leading-relaxed text-slate-200">{d.summary ?? d.abstract ?? "No summary yet."}</p></section>
      <section className="glass p-4"><h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-400">Ask about this paper</h3><AskChat paperId={id} /></section>
      <section>
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-400">Related papers</h3>
        {rel.loading ? <Spinner /> : (
          <ul className="space-y-2">{(rel.data ?? []).map((r) => (
            <li key={r.id}><button onClick={() => onOpen(r.id)} className="w-full rounded-xl bg-white/5 px-3 py-2 text-left text-sm hover:bg-white/10">{r.title}<span className="ml-2 text-xs text-slate-500">{r.year}</span></button></li>
          ))}</ul>
        )}
      </section>
    </div>
  );
}
