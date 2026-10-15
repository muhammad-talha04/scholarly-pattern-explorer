"use client";
import { useState } from "react";
import { saveToCollection, useCollections } from "@/lib/library";

export function SaveButton({ paperId }: { paperId: string }) {
  const collections = useCollections();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("Reading list");
  const [note, setNote] = useState("");
  return (
    <div className="relative">
      <button className="btn w-full" aria-expanded={open} onClick={() => setOpen((v) => !v)}>Save to collection</button>
      {open && (
        <div className="glass absolute right-0 z-20 mt-2 w-64 p-3 text-sm">
          <label className="block text-xs text-mist">Collection name
            <input className="input mt-1 w-full" value={name} onChange={(e) => setName(e.target.value)} aria-label="Collection name" />
          </label>
          {collections.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {collections.map((c) => <button key={c.id} className="chip hover:text-white" onClick={() => setName(c.name)}>{c.name}</button>)}
            </div>
          )}
          <button className="btn mt-3 w-full bg-sky-400/20" onClick={() => { saveToCollection(name, paperId); setNote(`Saved to ${name.trim() || "Reading list"}`); setOpen(false); }}>Save on this device</button>
        </div>
      )}
      {note && <p className="mt-1 text-xs text-emerald-300" role="status">{note}</p>}
    </div>
  );
}
