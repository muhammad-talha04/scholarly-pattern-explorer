"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api/client";
import type { PaperDetail } from "@/lib/api/types";
import { useApi } from "@/lib/useApi";
import { EmptyState, ErrorNote, LoadingBlock, PageHeader } from "@/components/ui";

export function ComparePage() {
  const sp = useSearchParams();
  const a = sp.get("a") ?? "", b = sp.get("b") ?? "";
  const left = useApi(() => (a ? api.paper(a) : Promise.resolve({ data: null as PaperDetail | null, source: "mock" as const })), [a]);
  const right = useApi(() => (b ? api.paper(b) : Promise.resolve({ data: null as PaperDetail | null, source: "mock" as const })), [b]);
  if (!a || !b) {
    return (
      <div>
        <PageHeader title="Compare" subtitle="Two papers, field by field. Pin them from search." />
        <EmptyState title="Pin two papers" body="Open Search, choose Compare on two results, then come back. The pair is remembered in this tab." action={<Link className="btn bg-accent/20" href="/search">Go to search</Link>} />
      </div>
    );
  }
  if ((left.loading && !left.data) || (right.loading && !right.data)) return <LoadingBlock label="Loading both papers" />;
  if (left.error || right.error || !left.data || !right.data) return <ErrorNote msg={left.error || right.error || "One of the papers could not be loaded"} onRetry={() => { left.reload(); right.reload(); }} />;
  const rows: [string, (p: PaperDetail) => React.ReactNode][] = [
    ["Year", (p) => p.year ?? "n.d."],
    ["Citations", (p) => p.cited_by.toLocaleString()],
    ["Authors", (p) => p.authors.join(", ") || "—"],
    ["Countries", (p) => p.countries.join(", ") || "—"],
    ["Topics", (p) => <Topics mine={p.topics} other={p === left.data ? right.data!.topics : left.data!.topics} />],
    ["One line", (p) => p.one_line_summary ?? "—"],
    ["Summary", (p) => p.summary ?? p.abstract ?? "No summary yet."],
  ];
  return (
    <div>
      <PageHeader title="Compare" subtitle="Side by side. Topics that only one paper carries are marked." />
      <div className="grid gap-4 lg:grid-cols-2">
        {[left.data, right.data].map((p) => (
          <article key={p.id} className="glass p-4">
            <h2 className="font-display text-2xl leading-snug text-white">{p.title}</h2>
            <a className="mt-2 inline-block text-sm text-accent underline-offset-2 hover:underline" href={`/search?paper=${encodeURIComponent(p.id)}&q=${encodeURIComponent(p.topics[0] ?? p.title)}`}>Open in search</a>
            {p.original_url && <a className="ml-3 text-sm text-accent underline-offset-2 hover:underline" href={p.original_url} target="_blank" rel="noopener noreferrer">Original</a>}
          </article>
        ))}
      </div>
      <div className="glass mt-4 overflow-x-auto">
        <table className="w-full min-w-[36rem] text-sm">
          <thead className="text-left text-xs uppercase text-mist"><tr><th className="p-3 w-28">Field</th><th className="p-3">Paper A</th><th className="p-3">Paper B</th></tr></thead>
          <tbody>
            {rows.map(([label, cell]) => (
              <tr key={label} className="border-t border-white/10 align-top">
                <th className="p-3 text-left font-medium text-mist">{label}</th>
                <td className="p-3 text-slate-100">{cell(left.data!)}</td>
                <td className="p-3 text-slate-100">{cell(right.data!)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Topics({ mine, other }: { mine: string[]; other: string[] }) {
  const only = new Set(mine.filter((t) => !other.includes(t)));
  if (!mine.length) return <>—</>;
  return <span className="flex flex-wrap gap-1">{mine.map((t) => <span key={t} className={`chip ${only.has(t) ? "border-gap/50 text-gap" : ""}`}>{t}</span>)}</span>;
}
