"use client";
import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api/client";
import type { PaperDetail } from "@/lib/api/types";
import { removeCollection, removePaper, useCollections } from "@/lib/library";
import { useApi } from "@/lib/useApi";
import { EmptyState, PageHeader } from "@/components/ui";
import { PaperPanel } from "@/features/search/PaperPanel";

export function CollectionsPage() {
  const collections = useCollections();
  const [open, setOpen] = useState<string | null>(null);
  return (
    <div>
      <PageHeader title="Saved" subtitle="Collections live in this browser only. Clearing site data removes them." />
      {collections.length === 0 ? (
        <EmptyState title="Nothing saved yet" body="Open a paper and choose Save to collection. A reading list is created the first time you save." action={<Link className="btn bg-accent/20" href="/search">Find a paper</Link>} />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {collections.map((c) => (
            <section key={c.id} className="glass p-4">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h2 className="font-display text-2xl text-white">{c.name}</h2>
                  <p className="text-xs text-mist">{c.paperIds.length} paper{c.paperIds.length === 1 ? "" : "s"} · saved {new Date(c.createdAt).toLocaleDateString()}</p>
                </div>
                <button className="chip hover:text-white" onClick={() => removeCollection(c.id)}>Delete</button>
              </div>
              <ul className="mt-3 space-y-2">
                {c.paperIds.map((id) => <SavedRow key={id} id={id} onOpen={setOpen} onRemove={() => removePaper(c.id, id)} />)}
              </ul>
            </section>
          ))}
        </div>
      )}
      <PaperPanel id={open} onClose={() => setOpen(null)} onOpen={setOpen} />
    </div>
  );
}

function SavedRow({ id, onOpen, onRemove }: { id: string; onOpen: (id: string) => void; onRemove: () => void }) {
  const p = useApi(() => api.paper(id), [id]);
  const title = (p.data as PaperDetail | undefined)?.title ?? id;
  return (
    <li className="flex items-center gap-2 rounded-xl bg-white/5 px-2 py-1.5">
      <button className="min-w-0 flex-1 truncate text-left text-sm hover:text-accent" onClick={() => onOpen(id)}>{title}</button>
      <button className="chip shrink-0 hover:text-white" onClick={onRemove} aria-label={`Remove ${title}`}>Remove</button>
    </li>
  );
}
