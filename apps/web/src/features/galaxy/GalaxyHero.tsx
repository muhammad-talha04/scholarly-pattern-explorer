"use client";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { api } from "@/lib/api/client";
import { buildTopicGraph } from "@/lib/graph";
import { useApi } from "@/lib/useApi";
import { useMotionPrefs } from "@/components/MotionProvider";
import { Galaxy2D } from "./Galaxy2D";
import { SearchBar } from "@/features/search/SearchBar";

const Galaxy3D = dynamic(() => import("./Galaxy3D"), { ssr: false, loading: () => <div className="h-full w-full animate-pulse bg-white/[0.02]" /> });

export function GalaxyHero() {
  const router = useRouter();
  const { lowPower } = useMotionPrefs();
  const [showGaps, setShowGaps] = useState(true);
  const pats = useApi(() => api.patterns(), []);
  const gaps = useApi(() => api.patterns({ trend: "gap" }), []);
  const graph = useMemo(() => buildTopicGraph(pats.data ?? [], gaps.data ?? []), [pats.data, gaps.data]);
  const pick = (t: string) => router.push(`/search?q=${encodeURIComponent(t)}`);
  return (
    <section className="relative -mx-4 -mt-20 h-[calc(100vh-1rem)] min-h-[620px] overflow-hidden">
      <div className="absolute inset-0">
        {graph.nodes.length > 0 && (lowPower ? <Galaxy2D {...graph} showGaps={showGaps} onPick={pick} /> : <Galaxy3D {...graph} showGaps={showGaps} onPick={pick} />)}
      </div>
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-ink/30 via-transparent to-ink" />
      <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8 }} className="pointer-events-none absolute inset-x-0 bottom-16 mx-auto max-w-3xl px-4 text-center">
        <h1 className="text-4xl font-semibold tracking-tight sm:text-6xl">
          Explore research <span className="bg-gradient-to-r from-sky-300 to-pink-300 bg-clip-text text-transparent">by meaning</span>
        </h1>
        <p className="mt-3 text-slate-400">Every glowing node is a topic, sized by support; lines show co-occurrence. Pink nodes are research gaps: fast-growing, still-small topics.</p>
        <div className="pointer-events-auto mt-6"><SearchBar big onSubmit={(q) => router.push(`/search?q=${encodeURIComponent(q)}`)} /></div>
        <label className="pointer-events-auto mt-4 inline-flex cursor-pointer items-center gap-2 text-sm text-slate-300">
          <input type="checkbox" checked={showGaps} onChange={(e) => setShowGaps(e.target.checked)} className="accent-pink-400" /> Highlight research gaps
          {gaps.data && <span className="chip">{gaps.data.length} gaps</span>}
        </label>
      </motion.div>
    </section>
  );
}
