"use client";
import { useState } from "react";
export function SearchBar({ initial = "", big = false, onSubmit }: { initial?: string; big?: boolean; onSubmit: (q: string) => void }) {
  const [q, setQ] = useState(initial);
  return (
    <form role="search" data-tour="search" onSubmit={(e) => { e.preventDefault(); if (q.trim()) onSubmit(q.trim()); }} className={`glass flex w-full min-w-0 items-center gap-2 ${big ? "p-2 pl-4 sm:pl-5" : "p-1.5 pl-3 sm:pl-4"}`}>
      <span aria-hidden className="shrink-0 text-slate-400">⌕</span>
      <input aria-label="Search papers" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by meaning" className={`min-w-0 flex-1 bg-transparent outline-none placeholder:text-slate-400 ${big ? "py-3 text-base sm:text-lg" : "py-2 text-sm"}`} />
      <button type="submit" className="btn shrink-0 bg-sky-400/20 px-3 hover:bg-sky-400/30 sm:px-4">Search</button>
    </form>
  );
}
