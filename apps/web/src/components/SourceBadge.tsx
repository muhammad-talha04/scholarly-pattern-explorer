"use client";
import { useEffect, useState } from "react";
import { onSourceChange, type Source } from "@/lib/api/client";
export function SourceBadge() {
  const [s, setS] = useState<Source | null>(null);
  useEffect(() => onSourceChange(setS), []);
  if (!s) return null;
  return <span className={`chip ${s === "mock" ? "border-amber-400/30 text-amber-300" : "border-emerald-400/30 text-emerald-300"}`} title={s === "mock" ? "API unreachable or route not implemented; showing fixtures" : "Live API"}>{s === "mock" ? "mock data" : "live"}</span>;
}
