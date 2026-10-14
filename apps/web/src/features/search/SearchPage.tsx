"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api/client";
import { useApi } from "@/lib/useApi";
import { ErrorNote, PageHeader, Spinner } from "@/components/ui";
import { SearchBar } from "./SearchBar";
import { ResultCard } from "./ResultCard";
import { PaperPanel } from "./PaperPanel";

export function SearchPage() {
  const sp = useSearchParams(), router = useRouter();
  const q = sp.get("q") ?? "", country = sp.get("country") ?? "", yearFrom = sp.get("year_from") ?? "";
  const [open, setOpen] = useState<string | null>(null);
  const countries = useApi(() => api.countries(), []);
  const res = useApi(() => (q ? api.search({ q, limit: 20, country: country || undefined, year_from: yearFrom ? Number(yearFrom) : undefined }) : Promise.resolve({ data: null, source: "mock" as const })), [q, country, yearFrom]);
  const nav = (patch: Record<string, string>) => {
    const p = new URLSearchParams(sp.toString()); Object.entries(patch).forEach(([k, v]) => (v ? p.set(k, v) : p.delete(k)));
    router.push(`/search?${p.toString()}`);
  };
  const thisYear = new Date().getFullYear();
  return (
    <div>
      <PageHeader title="Search" subtitle="Meaning-based search over the indexed papers." />
      <SearchBar key={q} initial={q} onSubmit={(v) => nav({ q: v })} />
      <div className="mt-3 flex flex-wrap gap-3 text-sm">
        <label className="flex items-center gap-2 text-slate-400">Country
          <select aria-label="Country filter" value={country} onChange={(e) => nav({ country: e.target.value })} className="input py-1.5">
            <option value="">All</option>{(countries.data ?? []).map((c) => <option key={c.code} value={c.code}>{c.name}</option>)}
          </select>
        </label>
        <label className="flex items-center gap-2 text-slate-400">From year
          <select aria-label="Year filter" value={yearFrom} onChange={(e) => nav({ year_from: e.target.value })} className="input py-1.5">
            <option value="">Any</option>{Array.from({ length: 12 }, (_, i) => thisYear - i).map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </label>
      </div>
      <div className="mt-6 grid gap-3 md:grid-cols-2">
        {!q && <p className="text-slate-400">Type a question or topic to begin.</p>}
        {res.loading && q && <Spinner />}
        {res.error && <ErrorNote msg={res.error} />}
        {res.data && res.data.results.length === 0 && <p className="text-slate-400">No papers match. Try removing filters.</p>}
        {res.data?.results.map((p, i) => <ResultCard key={p.id} paper={p} index={i} active={open === p.id} onOpen={setOpen} />)}
      </div>
      <PaperPanel id={open} onClose={() => setOpen(null)} onOpen={setOpen} />
    </div>
  );
}
