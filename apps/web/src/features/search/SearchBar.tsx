"use client";
import { useState } from "react";
export function SearchBar({ initial = "", big = false, onSubmit }: { initial?: string; big?: boolean; onSubmit: (q: string) => void }) {
  const [q, setQ] = useState(initial);
  return (
    <form role="search" data-tour="search" onSubmit={(e) => { e.preventDefault(); if (q.trim()) onSubmit(q.trim()); }} className={`${big ? "search-hero" : "glass"} relative z-30 flex w-full min-w-0 items-center gap-2 ${big ? "p-2 pl-4 sm:pl-5" : "p-1.5 pl-3 sm:pl-4"}`}>
      <span aria-hidden className="shrink-0 text-accent">⌕</span>
      <input aria-label="Search papers" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by meaning or topic" className={`min-w-0 flex-1 bg-transparent text-white outline-none placeholder:text-mist/80 ${big ? "py-3 text-base sm:text-lg" : "py-2 text-sm"}`} />
      <button type="submit" className={`btn shrink-0 px-3 sm:px-4 ${big ? "border-transparent bg-accent font-semibold text-ink hover:bg-accent/90" : "bg-accent/20 hover:bg-accent/30"}`}>Search</button>
    </form>
  );
}
