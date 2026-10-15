"use client";
import { motion } from "framer-motion";
import type { PaperSummary } from "@/lib/api/types";
import { toggleCompare, useCompare } from "@/lib/library";

export function ResultCard({ paper, onOpen, active, index = 0 }: { paper: PaperSummary; onOpen: (id: string) => void; active?: boolean; index?: number }) {
  const pinned = useCompare().includes(paper.id);
  return (
    <motion.article layout initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(index, 12) * 0.03 }}
      className={`glass p-4 ${active ? "border-sky-300/60" : ""}`}>
      <button onClick={() => onOpen(paper.id)} className="w-full text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-accent">
        <h3 className="font-medium leading-snug text-white">{paper.title}</h3>
        <p className="mt-1 text-xs text-mist">{paper.authors.slice(0, 4).join(", ")}{paper.authors.length > 4 ? " et al." : ""}</p>
        {paper.one_line_summary && <p className="mt-2 text-sm text-slate-200">{paper.one_line_summary}</p>}
        <div className="mt-3 flex flex-wrap gap-2 text-xs">
          {paper.year && <span className="chip">{paper.year}</span>}
          <span className="chip">{paper.cited_by.toLocaleString()} citations</span>
          {paper.score != null && <span className="chip text-sky-200">match {(paper.score * 100).toFixed(0)}%</span>}
        </div>
      </button>
      <button className={`btn mt-3 py-1 text-xs ${pinned ? "bg-pink-300/20" : ""}`} aria-pressed={pinned} onClick={() => toggleCompare(paper.id)}>
        {pinned ? "Unpin" : "Compare"}
      </button>
    </motion.article>
  );
}
