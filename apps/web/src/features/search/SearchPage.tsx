"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, searchPageSize } from "@/lib/api/client";
import { useApi } from "@/lib/useApi";
import { EmptyState, ErrorNote, PageHeader, Spinner } from "@/components/ui";
import { SearchBar } from "./SearchBar";
import { ResultCard } from "./ResultCard";
import { PaperPanel } from "./PaperPanel";
import Link from "next/link";

/** Render's free tier can take a minute or two to wake; give up after this and show the error state. */
export const SEARCH_TIMEOUT_MS = 120_000;

export function withTimeout<T>(p: Promise<T>, ms = SEARCH_TIMEOUT_MS): Promise<T> {
  let t: ReturnType<typeof setTimeout> | undefined;
  const timer = new Promise<never>((_, reject) => { t = setTimeout(() => reject(new Error("Search timed out. The server did not answer in time.")), ms); });
  return Promise.race([p, timer]).finally(() => clearTimeout(t));
}

export function SearchLoading() {
  return (
    <div role="status" data-testid="search-loading" className="md:col-span-2 flex flex-col gap-1 text-sm text-mist">
      <span className="flex items-center gap-2"><Spinner /> Searching</span>
      <span className="text-xs text-slate-400">The search server may take a moment to wake up if nobody has used it recently. First searches can take up to a minute or two.</span>
    </div>
  );
}

export function SearchError({ msg, onRetry }: { msg: string; onRetry: () => void }) {
  return (
    <div data-testid="search-error" className="md:col-span-2">
      <ErrorNote msg={`Search is unavailable right now. ${msg}`} onRetry={onRetry} />
    </div>
  );
}

export function NoCloseMatches({ filtered, onClear }: { filtered: boolean; onClear: () => void }) {
  return (
    <div data-testid="search-no-matches" className="md:col-span-2">
      <EmptyState title="No close matches" body="Nothing in this sample is a close match. Try different or broader words, or browse topics instead."
        action={<div className="flex flex-wrap justify-center gap-2">
          <Link href="/patterns" className="btn bg-accent/20">Browse patterns and gaps</Link>
          <Link href="/timeline" className="btn">See topics over time</Link>
          {filtered && <button className="btn" onClick={onClear}>Clear filters</button>}
        </div>} />
    </div>
  );
}

function bounded(raw: string | null, fallback: number, min: number, max: number) {
  if (raw == null || raw.trim() === "") return fallback;
  const n = Number(raw);
  if (!Number.isFinite(n)) return fallback;
  return Math.min(max, Math.max(min, Math.floor(n)));
}

export function SearchPage() {
  const sp = useSearchParams(), router = useRouter();
  const q = sp.get("q") ?? "", country = sp.get("country") ?? "", yearFrom = sp.get("year_from") ?? "";
  const limit = bounded(sp.get("limit"), searchPageSize(), 1, 10000);
  const offset = bounded(sp.get("offset"), 0, 0, 1_000_000);
  const paperQ = sp.get("paper");
  const [open, setOpen] = useState<string | null>(paperQ);
  useEffect(() => { if (paperQ) setOpen(paperQ); }, [paperQ]);
  const countries = useApi(() => api.countries(), []);
  const res = useApi(() => (q ? withTimeout(api.search({ q, limit, offset, country: country || undefined, year_from: yearFrom ? Number(yearFrom) : undefined })) : Promise.resolve({ data: null, source: "mock" as const })), [q, country, yearFrom, limit, offset]);
  const nav = (patch: Record<string, string>, keepOffset = false) => {
    const p = new URLSearchParams(sp.toString());
    Object.entries(patch).forEach(([k, v]) => (v ? p.set(k, v) : p.delete(k)));
    if (!keepOffset) p.delete("offset");
    router.push(`/search?${p.toString()}`);
  };
  const thisYear = new Date().getFullYear();
  return (
    <div>
      <PageHeader title="Search" subtitle="Search AI research papers by keyword and topic. Meaning-based search is being upgraded. Pin two results to compare them." />
      <SearchBar key={q} initial={q} onSubmit={(v) => nav({ q: v })} />
      <div className="mt-3 flex flex-wrap gap-3 text-sm">
        <label className="flex items-center gap-2 text-mist">Country
          <select aria-label="Country filter" value={country} onChange={(e) => nav({ country: e.target.value })} className="input py-1.5">
            <option value="">All</option>{(countries.data ?? []).map((c) => <option key={c.code} value={c.code}>{c.name}</option>)}
          </select>
        </label>
        <label className="flex items-center gap-2 text-mist">From year
          <select aria-label="Year filter" value={yearFrom} onChange={(e) => nav({ year_from: e.target.value })} className="input py-1.5">
            <option value="">Any</option>{Array.from({ length: 12 }, (_, i) => thisYear - i).map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </label>
      </div>
      <div className="mt-6 grid gap-3 md:grid-cols-2">
        {!q && <div className="md:col-span-2"><EmptyState title="Ask a question" body="Try a topic in plain language, for example “privacy in federated learning”. Filters sit above the results." /></div>}
        {res.loading && q && <SearchLoading />}
        {q && !res.loading && res.error && <SearchError msg={res.error} onRetry={res.reload} />}
        {q && !res.loading && !res.error && res.data && res.data.results.length === 0 && <NoCloseMatches filtered={!!(country || yearFrom)} onClear={() => nav({ country: "", year_from: "" })} />}
        {!res.error && res.data?.results.map((p, i) => <ResultCard key={p.id} paper={p} index={i} active={open === p.id} onOpen={setOpen} />)}
      </div>
      {q && res.data && res.data.results.length > 0 && <SearchPager data={res.data} offset={offset} limit={limit} onPage={(next) => nav({ offset: next > 0 ? String(next) : "" }, true)} />}
      <PaperPanel id={open} onClose={() => setOpen(null)} onOpen={setOpen} />
    </div>
  );
}

function SearchPager({ data, offset, limit, onPage }: {
  data: { results: unknown[]; total?: number; limit?: number; offset?: number };
  offset: number;
  limit: number;
  onPage: (offset: number) => void;
}) {
  const pageOffset = data.offset ?? offset;
  const pageLimit = data.limit ?? limit;
  const shown = data.results.length;
  const total = data.total;
  const from = shown === 0 ? 0 : pageOffset + 1;
  const to = pageOffset + shown;
  const hasTotal = typeof total === "number";
  const prev = Math.max(0, pageOffset - pageLimit);
  const next = pageOffset + shown;
  return (
    <div className="mt-4 flex flex-wrap items-center gap-3 text-sm text-mist">
      <p>{hasTotal ? `Showing ${from}–${to} of ${total}` : `Showing ${from}–${to}`}</p>
      {hasTotal && total > pageLimit && (
        <div className="flex gap-2">
          <button className="btn px-3 py-1.5 disabled:pointer-events-none disabled:opacity-40" disabled={pageOffset <= 0} onClick={() => onPage(prev)}>Previous</button>
          <button className="btn px-3 py-1.5 disabled:pointer-events-none disabled:opacity-40" disabled={next >= total} onClick={() => onPage(next)}>Next</button>
        </div>
      )}
    </div>
  );
}
