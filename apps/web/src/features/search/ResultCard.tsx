"use client";
import { motion } from "framer-motion";
import type { PaperSummary } from "@/lib/api/types";
export function ResultCard({ paper, onOpen, active, index = 0 }: { paper: PaperSummary; onOpen: (id: string) => void; active?: boolean; index?: number }) {
  return (
    <motion.button layout initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.03 }}
      onClick={() => onOpen(paper.id)} className={`glass w-full p-4 text-left transition hover:border-sky-300/40 ${active ? "border-sky-300/60" : ""}`}>
      <h3 className="font-medium leading-snug">{paper.title}</h3>
      <p className="mt-1 text-xs text-slate-400">{paper.authors.slice(0, 4).join(", ")}{paper.authors.length > 4 ? " et al." : ""}</p>
      {paper.one_line_summary && <p className="mt-2 text-sm text-slate-300">{paper.one_line_summary}</p>}
      <div className="mt-3 flex gap-2 text-xs">
        {paper.year && <span className="chip">{paper.year}</span>}
        <span className="chip">{paper.cited_by.toLocaleString()} citations</span>
        {paper.score != null && <span className="chip text-sky-300">match {(paper.score * 100).toFixed(0)}%</span>}
      </div>
    </motion.button>
  );
}
