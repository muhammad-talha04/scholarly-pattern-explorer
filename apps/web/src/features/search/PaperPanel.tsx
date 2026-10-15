"use client";
import { AnimatePresence, motion } from "framer-motion";
import { api } from "@/lib/api/client";
import { toggleCompare, useCompare } from "@/lib/library";
import { useApi } from "@/lib/useApi";
import { ErrorNote, Spinner } from "@/components/ui";
import { AskChat } from "./AskChat";
import { CitationMap } from "./CitationMap";
import { SaveButton } from "./SaveButton";

export function PaperPanel({ id, onClose, onOpen }: { id: string | null; onClose: () => void; onOpen: (id: string) => void }) {
  return (
    <AnimatePresence>
      {id && (
        <motion.aside key="panel" initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ type: "spring", damping: 28, stiffness: 240 }}
          className="fixed bottom-0 right-0 top-14 z-30 w-full overflow-y-auto border-l border-white/10 bg-ink/95 p-4 backdrop-blur-2xl sm:max-w-xl sm:p-6" aria-label="Paper details">
          <button onClick={onClose} className="chip float-right hover:text-white" aria-label="Close panel">Close</button>
          <PaperBody id={id} onOpen={onOpen} />
        </motion.aside>
      )}
    </AnimatePresence>
  );
}

function PaperBody({ id, onOpen }: { id: string; onOpen: (id: string) => void }) {
  const p = useApi(() => api.paper(id), [id]);
  const rel = useApi(() => api.related(id), [id]);
  const pinned = useCompare().includes(id);
  if (p.loading) return <div className="pt-8"><Spinner /></div>;
  if (p.error || !p.data) return <ErrorNote msg={p.error ?? "not found"} onRetry={p.reload} />;
  const d = p.data, link = d.original_url ?? d.openalex_url;
  return (
    <div className="clear-both space-y-6">
      <div>
        <h2 className="pr-16 font-display text-2xl leading-snug text-white">{d.title}</h2>
        <p className="mt-1 text-sm text-mist">{d.authors.join(", ")} · {d.year ?? "n.d."} · {d.cited_by} citations</p>
        <div className="mt-2 flex flex-wrap gap-1.5">{d.topics.map((t) => <span key={t} className="chip">{t}</span>)}{d.countries.map((c) => <span key={c} className="chip text-sky-200">{c}</span>)}</div>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        {link && (
          <a href={link} target="_blank" rel="noopener noreferrer" className="flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-sky-400 to-violet-400 px-4 py-3 font-semibold text-ink shadow-glow transition hover:brightness-110">
            Read original paper
          </a>
        )}
        <button className={`btn ${pinned ? "bg-pink-300/20" : ""}`} aria-pressed={pinned} onClick={() => toggleCompare(id)}>{pinned ? "Pinned for compare" : "Pin to compare"}</button>
        <SaveButton paperId={id} />
      </div>
      <section>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-widest text-mist">Summary</h3>
        <p className="text-sm leading-relaxed text-slate-100">{d.summary ?? d.abstract ?? "No summary yet."}</p>
      </section>
      <section className="glass p-4">
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-widest text-mist">Ask about this paper</h3>
        <AskChat paperId={id} />
      </section>
      <section>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-widest text-mist">Related papers</h3>
        {rel.loading ? <Spinner /> : rel.error ? <ErrorNote msg={rel.error} onRetry={rel.reload} /> : (
          <>
            <CitationMap center={d.title} related={rel.data ?? []} onOpen={onOpen} />
            <ul className="mt-3 space-y-2">{(rel.data ?? []).map((r) => (
              <li key={r.id}><button onClick={() => onOpen(r.id)} className="w-full rounded-xl bg-white/5 px-3 py-2 text-left text-sm hover:bg-white/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent">{r.title}<span className="ml-2 text-xs text-slate-400">{r.year}</span></button></li>
            ))}</ul>
          </>
        )}
      </section>
    </div>
  );
}
