"use client";
import Link from "next/link";
import { clearCompare, useCompare } from "@/lib/library";

export function CompareTray() {
  const ids = useCompare();
  if (ids.length === 0) return null;
  const href = `/compare?a=${encodeURIComponent(ids[0])}&b=${encodeURIComponent(ids[1] ?? "")}`;
  return (
    <div className="fixed inset-x-0 bottom-0 z-30 border-t border-white/10 bg-ink/90 px-3 py-3 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-3">
        <p className="text-sm text-mist">{ids.length === 1 ? "1 paper pinned" : "2 papers pinned"} for compare</p>
        <Link href={href} className={`btn ${ids.length < 2 ? "pointer-events-none opacity-40" : "bg-accent/20"}`} aria-disabled={ids.length < 2}>Open side by side</Link>
        <button className="btn" onClick={clearCompare}>Clear</button>
      </div>
    </div>
  );
}
