"use client";
import { motion } from "framer-motion";
import type { Counting } from "@/lib/api/types";

export const COUNTING_LABEL: Record<Counting, string> = {
  fractional: "Fractional counting: each paper splits 1 credit across its countries",
  per_country: "Per-country counting: each collaboration pair is weighted 1/n",
  full: "Full counting: each country on a paper gets 1 full credit",
};

/** Short button names plus a plain-language tooltip for each counting method. */
export const OPTIONS: { id: Counting; label: string; hint: string }[] = [
  { id: "fractional", label: "Shared credit", hint: "A paper with authors from 3 countries gives each country 1/3. Totals add up to the real number of papers." },
  { id: "per_country", label: "Split per pair", hint: "Collaboration arcs: each country pair on a paper is weighted 1/n, so big multi-country papers don't dominate." },
  { id: "full", label: "Full credit", hint: "Every country on a paper gets 1 whole paper. Shows reach, but international papers are counted more than once." },
];

export function CountingToggle({ value, onChange }: { value: Counting; onChange: (c: Counting) => void }) {
  return (
    <div className="flex w-full min-w-0 basis-full flex-col gap-2">
      <div role="radiogroup" aria-label="Counting method" className="glass flex w-fit max-w-full flex-wrap self-end p-1">
        {OPTIONS.map((c) => (
          <button key={c.id} role="radio" aria-checked={value === c.id} onClick={() => onChange(c.id)} title={c.hint} className="relative whitespace-nowrap rounded-lg px-3 py-1.5 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-accent">
            {value === c.id && <motion.span layoutId="count-pill" className="absolute inset-0 rounded-lg bg-accent/25" />}
            <span className="relative">{c.label}</span>
          </button>
        ))}
      </div>
      <p data-testid="counting-label" className="w-full min-w-0 whitespace-normal text-pretty text-left text-xs leading-relaxed text-mist sm:text-right">Showing: <span className="text-accent">{COUNTING_LABEL[value]}</span><span className="block">{OPTIONS.find((o) => o.id === value)?.hint}</span></p>
    </div>
  );
}
