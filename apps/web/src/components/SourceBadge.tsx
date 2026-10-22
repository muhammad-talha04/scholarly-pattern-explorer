"use client";
import { useEffect, useState } from "react";
import { api, onSourceChange, prefersFixtures, type Source } from "@/lib/api/client";
import { FIXTURE_COUNT } from "@/lib/api/mock";
import { useApi } from "@/lib/useApi";

export function SourceBadge() {
  const demo = prefersFixtures();
  const [s, setS] = useState<Source | null>(demo ? "mock" : null);
  useEffect(() => onSourceChange(setS), []);
  const stats = useApi(
    () => (demo ? Promise.resolve({ data: null, source: "mock" as const }) : api.stats()),
    [demo],
  );
  if (demo || s === "mock") {
    return (
      <span className="chip border-accent/50 text-accent" title="The API is not configured, so this is the built-in sample.">
        Demo data
      </span>
    );
  }
  if (s === "live" && typeof stats.data?.papers === "number") {
    return (
      <span className="chip border-up/40 text-up" title="Papers indexed by the API">
        {stats.data.papers.toLocaleString()} papers
      </span>
    );
  }
  if (s === "live") return <span className="chip border-up/40 text-up" title="Live API">live</span>;
  return null;
}

/** One sentence under the nav while the UI is on the built-in sample. */
export function DemoNote() {
  const demo = prefersFixtures();
  const [s, setS] = useState<Source | null>(demo ? "mock" : null);
  useEffect(() => onSourceChange(setS), []);
  if (!demo && s !== "mock") return null;
  return (
    <p data-demo-note className="border-t border-white/10 px-3 py-1.5 text-center text-xs leading-snug text-mist sm:px-4">
      Demo data: {FIXTURE_COUNT} sample papers. Titles open an OpenAlex search, not a publisher page.
    </p>
  );
}
