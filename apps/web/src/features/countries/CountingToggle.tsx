"use client";
import { motion } from "framer-motion";
import type { Counting } from "@/lib/api/types";

export const COUNTING_LABEL: Record<Counting, string> = {
  fractional: "Fractional counting: each paper splits 1 credit across its countries",
  per_country: "Per-country counting: each collaboration pair is weighted 1/n",
  full: "Full counting: each country on a paper gets 1 full credit",
};

const OPTIONS: { id: Counting; label: string }[] = [
  { id: "fractional", label: "fractional" },
  { id: "per_country", label: "per country" },
  { id: "full", label: "full" },
];

export function CountingToggle({ value, onChange }: { value: Counting; onChange: (c: Counting) => void }) {
  return (
    <div className="flex w-full min-w-0 basis-full flex-col gap-2">
      <div role="radiogroup" aria-label="Counting method" className="glass flex w-fit max-w-full flex-wrap self-end p-1">
        {OPTIONS.map((c) => (
          <button key={c.id} role="radio" aria-checked={value === c.id} onClick={() => onChange(c.id)} className="relative whitespace-nowrap rounded-lg px-3 py-1.5 text-sm capitalize focus:outline-none focus-visible:ring-2 focus-visible:ring-accent">
            {value === c.id && <motion.span layoutId="count-pill" className="absolute inset-0 rounded-lg bg-accent/25" />}
            <span className="relative">{c.label}</span>
          </button>
        ))}
      </div>
      <p data-testid="counting-label" className="w-full min-w-0 whitespace-normal text-pretty text-left text-xs leading-relaxed text-mist sm:text-right">Showing: <span className="text-accent">{COUNTING_LABEL[value]}</span></p>
    </div>
  );
}
