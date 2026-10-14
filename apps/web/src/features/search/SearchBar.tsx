"use client";
import { useState } from "react";
export function SearchBar({ initial = "", big = false, onSubmit }: { initial?: string; big?: boolean; onSubmit: (q: string) => void }) {
  const [q, setQ] = useState(initial);
  return (
    <form role="search" onSubmit={(e) => { e.preventDefault(); if (q.trim()) onSubmit(q.trim()); }} className={`glass flex items-center gap-2 ${big ? "p-2 pl-5" : "p-1.5 pl-4"}`}>
      <span aria-hidden className="text-slate-500">⌕</span>
      <input aria-label="Search papers" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search papers by meaning, e.g. “privacy in federated learning”"
        className={`flex-1 bg-transparent outline-none placeholder:text-slate-500 ${big ? "py-3 text-lg" : "py-2 text-sm"}`} />
      <button type="submit" className="btn bg-sky-500/20 hover:bg-sky-500/30">Search</button>
    </form>
  );
}
