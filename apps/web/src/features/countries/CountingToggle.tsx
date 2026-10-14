"use client";
import { motion } from "framer-motion";
import type { Counting } from "@/lib/api/types";
export const COUNTING_LABEL: Record<Counting, string> = {
  fractional: "Fractional counting: each paper splits 1 credit across its countries",
  full: "Full counting: each country on a paper gets 1 full credit",
};
export function CountingToggle({ value, onChange }: { value: Counting; onChange: (c: Counting) => void }) {
  return (
    <div className="flex flex-col items-end gap-1">
      <div role="radiogroup" aria-label="Counting method" className="glass relative flex p-1">
        {(["fractional", "full"] as const).map((c) => (
          <button key={c} role="radio" aria-checked={value === c} onClick={() => onChange(c)} className="relative px-4 py-1.5 text-sm capitalize">
            {value === c && <motion.span layoutId="count-pill" className="absolute inset-0 rounded-lg bg-sky-500/25" />}
            <span className="relative">{c}</span>
          </button>
        ))}
      </div>
      <p data-testid="counting-label" className="text-xs text-slate-400">Showing: <span className="text-sky-300">{COUNTING_LABEL[value]}</span></p>
    </div>
  );
}
