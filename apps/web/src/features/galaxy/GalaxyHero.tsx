"use client";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { api, prefersFixtures } from "@/lib/api/client";
import type { GalaxyGraph } from "@/lib/api/types";
import { buildTopicGraph, type TopicLink, type TopicNode } from "@/lib/graph";
import { useApi } from "@/lib/useApi";
import { useMotionPrefs } from "@/components/MotionProvider";
import { EmptyState, ErrorNote, Spinner, StarMark } from "@/components/ui";
import { Galaxy2D } from "./Galaxy2D";
import { positionNodes, type Positioned } from "./layout";
import { SearchBar } from "@/features/search/SearchBar";

const Galaxy3D = dynamic(() => import("./Galaxy3D"), { ssr: false, loading: () => <GalaxyLoading /> });

type Placed = TopicNode & { pos?: [number, number, number] };

function project(graph: { nodes: TopicNode[]; links: TopicLink[] }, galaxy: GalaxyGraph | undefined, useCoords: boolean): { nodes: Placed[]; links: TopicLink[] } {
  if (!useCoords || !galaxy?.nodes.length) return { nodes: positionNodes(graph.nodes), links: graph.links };
  const gaps = new Map(graph.nodes.filter((n) => n.gap).map((n) => [n.id, n]));
  const clusters = new Map(galaxy.clusters.map((c) => [c.id, c.name]));
  const nodes: Positioned[] = galaxy.nodes.map((n) => ({
    id: n.topic_name,
    support: n.support || gaps.get(n.topic_name)?.support || 0.05,
    gap: gaps.has(n.topic_name),
    gapScore: gaps.get(n.topic_name)?.gapScore,
    cluster: clusters.get(n.cluster_id),
    pos: [n.x, n.y, n.z],
  }));
  const links = galaxy.links?.length ? galaxy.links : graph.links;
  return { nodes, links };
}

export function GalaxyHero() {
  const router = useRouter();
  const { lowPower } = useMotionPrefs();
  const [showGaps, setShowGaps] = useState(true);
  const [focus, setFocus] = useState<string | null>(null);
  const [previewEmpty, setPreviewEmpty] = useState(false);
  useEffect(() => { setPreviewEmpty(new URLSearchParams(window.location.search).get("preview") === "empty"); }, []);
  const pats = useApi(() => api.patterns(), []);
  const gaps = useApi(() => api.patterns({ trend: "gap" }), []);
  const galaxy = useApi(() => api.galaxy(), []);
  const graph = useMemo(() => buildTopicGraph(pats.data ?? [], gaps.data ?? []), [pats.data, gaps.data]);
  const useCoords = galaxy.source === "live" || (galaxy.source === "mock" && (prefersFixtures() || pats.source !== "live"));
  const view = useMemo(() => project(graph, galaxy.data, !!useCoords), [graph, galaxy.data, useCoords]);
  const loading = (pats.loading && !pats.data) || (galaxy.loading && !galaxy.data);
  const pick = (t: string) => router.push(`/search?q=${encodeURIComponent(t)}`);
  return (
    <section className="relative -mx-3 -mt-20 h-[100dvh] min-h-[640px] overflow-hidden sm:-mx-4">
      <div className="absolute inset-0">
        {pats.error && !pats.data ? (
          <div className="flex h-full items-center justify-center px-6 pt-24"><ErrorNote msg={pats.error} onRetry={pats.reload} /></div>
        ) : loading && !previewEmpty ? <GalaxyLoading /> : (previewEmpty || view.nodes.length === 0) ? (
          <div className="flex h-full items-center justify-center px-6 pt-28" data-testid="galaxy-empty">
            <EmptyState title="No topics in this snapshot" body="The galaxy fills in when the pattern miner publishes itemsets. You can still search papers, or open Patterns once a run has landed." action={<Link href="/search" className="btn bg-sky-400/20">Search papers</Link>} />
          </div>
        ) : lowPower ? (
          <Galaxy2D nodes={view.nodes} links={view.links} showGaps={showGaps} focus={focus} onFocus={setFocus} onPick={pick} />
        ) : (
          <Galaxy3D nodes={view.nodes} links={view.links} showGaps={showGaps} focus={focus} onFocus={setFocus} onPick={pick} />
        )}
      </div>
      <div className="pointer-events-none absolute inset-x-0 top-0 z-20 h-40 bg-gradient-to-b from-ink via-ink/70 to-transparent" />
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }} className="pointer-events-none absolute inset-x-0 top-[4.5rem] z-20 mx-auto max-w-xl px-3 sm:px-4">
        <div className="pointer-events-auto glass px-4 py-4 text-center sm:px-6">
          <h1 className="font-display text-3xl font-medium leading-tight tracking-tight text-white sm:text-5xl">
            Explore research <span className="text-accent">by meaning</span>
          </h1>
          <p className="mx-auto mt-2 hidden max-w-md text-sm text-mist sm:block">Nodes are topics. Lines are papers that share them. Pink marks a research gap: growing fast, still small.</p>
          <div className="mt-3"><SearchBar big onSubmit={(q) => router.push(`/search?q=${encodeURIComponent(q)}`)} /></div>
        </div>
      </motion.div>
      <div className="absolute inset-x-0 bottom-3 z-20 flex flex-wrap items-center justify-between gap-2 px-3 sm:px-5">
        <label className="glass inline-flex cursor-pointer items-center gap-2 px-3 py-2 text-sm text-mist">
          <input type="checkbox" checked={showGaps} onChange={(e) => setShowGaps(e.target.checked)} className="accent-pink-300" />
          Highlight gaps
          {gaps.data && <span className="chip">{gaps.data.length}</span>}
        </label>
        <details className="glass max-h-40 overflow-auto px-3 py-2 text-sm text-mist">
          <summary className="cursor-pointer text-white">Topics ({view.nodes.length})</summary>
          <ul className="mt-2 max-h-28 space-y-1 overflow-auto">
            {view.nodes.map((n) => (
              <li key={n.id}>
                <button className="w-full rounded-lg px-2 py-1 text-left hover:bg-white/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent" onClick={() => { setFocus(n.id); }}>
                  {n.id}{showGaps && n.gap ? " · gap" : ""}
                </button>
              </li>
            ))}
          </ul>
        </details>
      </div>
    </section>
  );
}

export function GalaxyLoading() {
  return (
    <div role="status" className="flex h-full flex-col items-center justify-center gap-4 bg-[radial-gradient(ellipse_at_center,rgba(125,211,252,0.16),transparent_55%)] text-sm text-mist">
      <StarMark />
      <div className="flex items-center gap-2"><Spinner /> Charting topics</div>
    </div>
  );
}
