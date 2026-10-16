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
import { positionNodes } from "./layout";
import { SearchBar } from "@/features/search/SearchBar";
import { galaxyColor } from "@/lib/palette";

const SUGGESTIONS = ["Protein folding", "Climate modelling", "Large language models"];
import { centroid, freshPaperIds, type PlexusPose, type Star } from "./stars";

const Galaxy3D = dynamic(() => import("./Galaxy3D"), { ssr: false, loading: () => <GalaxyPlaceholder /> });

/** The hero only needs a sample of the graph; full-graph views keep asking for everything. */
export const HERO_GALAXY_LIMIT = 600;

/** True once the browser has painted and gone idle, so the WebGL bundle never competes with the hero text. */
export function useAfterIdle(): boolean {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    let idle: number | undefined;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const raf = requestAnimationFrame(() => {
      const w = window as Window & { requestIdleCallback?: (cb: () => void, o?: { timeout: number }) => number };
      if (w.requestIdleCallback) idle = w.requestIdleCallback(() => setReady(true), { timeout: 2000 });
      else timer = setTimeout(() => setReady(true), 200);
    });
    return () => {
      cancelAnimationFrame(raf);
      const w = window as Window & { cancelIdleCallback?: (id: number) => void };
      if (idle !== undefined) w.cancelIdleCallback?.(idle);
      if (timer) clearTimeout(timer);
    };
  }, []);
  return ready;
}

/** Static stand-in that fills the same absolute box as the canvas, so swapping it in causes no layout shift. */
export function GalaxyPlaceholder() {
  return <div data-testid="galaxy-placeholder" aria-hidden className="absolute inset-0 bg-[radial-gradient(ellipse_at_70%_45%,rgba(255,190,120,0.10),transparent_60%)]" />;
}

function withCenters(nodes: Star[]): Star[] {
  const groups = new Map<string, Star[]>();
  for (const n of nodes) {
    const list = groups.get(n.clusterId) ?? [];
    list.push(n);
    groups.set(n.clusterId, list);
  }
  const centers = new Map<string, [number, number, number]>();
  for (const [id, list] of groups) centers.set(id, centroid(list));
  return nodes.map((n) => ({ ...n, center: centers.get(n.clusterId) ?? n.pos }));
}

function project(graph: { nodes: TopicNode[]; links: TopicLink[] }, galaxy: GalaxyGraph | undefined, useCoords: boolean): { nodes: Star[]; links: TopicLink[] } {
  const gNodes = Array.isArray(galaxy?.nodes) ? galaxy.nodes : [];
  const clusterById = new Map((Array.isArray(galaxy?.clusters) ? galaxy.clusters : []).map((c) => [c.id, c]));
  if (!useCoords || gNodes.length === 0) {
    const placed = positionNodes(graph.nodes);
    return {
      nodes: withCenters(placed.map((n) => ({
        id: n.id, support: n.support, gap: n.gap, gapScore: n.gapScore, cluster: n.cluster,
        clusterId: n.id, colorIndex: undefined, emerging: 0, pos: n.pos, center: n.pos,
      }))),
      links: graph.links,
    };
  }
  const gaps = new Map(graph.nodes.filter((n) => n.gap).map((n) => [n.id, n]));
  const nodes = withCenters(gNodes.map((n) => {
    const cluster = clusterById.get(n.cluster_id);
    return {
      id: n.topic_name,
      support: n.support || gaps.get(n.topic_name)?.support || 0.05,
      gap: gaps.has(n.topic_name),
      gapScore: gaps.get(n.topic_name)?.gapScore,
      cluster: cluster?.name,
      clusterId: n.cluster_id,
      colorIndex: n.color_index ?? cluster?.color_index,
      emerging: cluster?.emerging_score ?? 0,
      pos: [n.x, n.y, n.z] as [number, number, number],
      center: [n.x, n.y, n.z] as [number, number, number],
    };
  }));
  const linkList = Array.isArray(galaxy?.links) ? galaxy.links : [];
  const links = linkList.length ? linkList : graph.links;
  return { nodes, links };
}

export function GalaxyHero() {
  const router = useRouter();
  const { lowPower } = useMotionPrefs();
  const [showGaps, setShowGaps] = useState(true);
  const [focus, setFocus] = useState<string | null>(null);
  const [clusterQuery, setClusterQuery] = useState<string | null>(null);
  const [previewEmpty, setPreviewEmpty] = useState(false);
  const [pose, setPose] = useState<PlexusPose>(null);
  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    setPreviewEmpty(q.get("preview") === "empty");
    setClusterQuery(q.get("cluster"));
    const plexus = q.get("plexus");
    setPose(plexus === "in" || plexus === "out" ? plexus : null);
  }, []);
  const pats = useApi(() => api.patterns(), []);
  const gaps = useApi(() => api.patterns({ trend: "gap" }), []);
  const galaxy = useApi(() => api.galaxy(HERO_GALAXY_LIMIT), []);
  const canvasReady = useAfterIdle();
  const graph = useMemo(() => buildTopicGraph(pats.data ?? [], gaps.data ?? []), [pats.data, gaps.data]);
  const useCoords = galaxy.source === "live" || (galaxy.source === "mock" && (prefersFixtures() || pats.source !== "live"));
  const view = useMemo(() => project(graph, galaxy.data, !!useCoords), [graph, galaxy.data, useCoords]);
  const fresh = useMemo(() => new Set(view.nodes.length ? freshPaperIds(view.nodes.map((n) => n.id)) : []), [view.nodes]);
  const stars = useMemo(() => view.nodes.map((n) => ({ ...n, fresh: fresh.has(n.id) })), [view.nodes, fresh]);
  const highlight = useMemo(() => {
    if (!clusterQuery) return null;
    const q = clusterQuery.toLowerCase();
    const byName = stars.filter((n) => n.cluster?.toLowerCase() === q);
    const picked = byName.length ? byName : stars.filter((n) => n.id.toLowerCase().includes(q) || n.cluster?.toLowerCase().includes(q));
    return picked.length ? new Set(picked.map((n) => n.id)) : null;
  }, [clusterQuery, stars]);
  const clusterLegend = useMemo(() => {
    const rows: { name: string; color: string }[] = [];
    for (const n of stars) {
      if (!n.cluster || rows.some((r) => r.name === n.cluster)) continue;
      rows.push({ name: n.cluster, color: galaxyColor(n.colorIndex, n.clusterId) });
    }
    return rows;
  }, [stars]);
  const loading = (pats.loading && !pats.data) || (galaxy.loading && !galaxy.data);
  const pick = (t: string) => router.push(`/search?q=${encodeURIComponent(t)}`);
  const sky = pats.error && !pats.data ? (
    <div className="flex h-full items-center justify-center px-6 pt-24"><ErrorNote msg={pats.error} onRetry={pats.reload} /></div>
  ) : loading && !previewEmpty ? <GalaxyLoading /> : (previewEmpty || view.nodes.length === 0) ? (
    <div className="flex h-full items-center justify-center px-6 pt-28" data-testid="galaxy-empty">
      <EmptyState title="No papers in this snapshot" body="The galaxy groups papers by theme once they are indexed. You can still search, or open Patterns once a run has landed." action={<Link href="/search" className="btn bg-accent/20">Search papers</Link>} />
    </div>
  ) : lowPower ? (
    <Galaxy2D nodes={stars} links={view.links} showGaps={showGaps} focus={focus} highlight={highlight} pose={pose} onFocus={setFocus} onHighlight={(name) => setClusterQuery(name ?? null)} onPick={pick} />
  ) : !canvasReady ? <GalaxyPlaceholder /> : (
    <Galaxy3D nodes={stars} links={view.links} showGaps={showGaps} focus={focus} highlight={highlight} pose={pose} onFocus={setFocus} onHighlight={(name) => setClusterQuery(name ?? null)} onPick={pick} />
  );
  return (
    <section className="relative -mx-3 -mt-20 h-[100dvh] min-h-[640px] overflow-hidden sm:-mx-4">
      <div className="absolute inset-0 z-0">{sky}</div>
      <div aria-hidden className="hero-scrim pointer-events-none absolute inset-0 z-10" />
      <div className="pointer-events-none absolute inset-x-0 top-0 z-20 h-24 bg-gradient-to-b from-ink to-transparent" />
      <motion.div initial={false} className="pointer-events-none relative z-30 flex h-full flex-col justify-start px-4 pb-8 pt-28 sm:px-8 lg:w-[54%] lg:justify-center lg:pb-16 lg:pt-24">
        <div className="pointer-events-auto max-w-xl text-left">
          <p className="font-mono text-[11px] font-medium tracking-[0.18em] text-accent">OPENALEX · EMBEDDINGS · COSINE SIMILARITY</p>
          <h1 className="mt-3 font-sans text-4xl font-bold leading-[1.05] tracking-tight text-white sm:text-6xl">
            Explore AI research <span className="text-accent">by topic</span>
          </h1>
          <p className="mt-4 max-w-md text-sm text-mist sm:text-base">Each dot is a paper. Nearby dots have similar wording, and colours mark clusters of related papers.</p>
          <p data-testid="hero-caption" className="mt-2 max-w-md text-xs text-slate-400">Dot positions show topic clusters; connecting lines are decorative.</p>
          <div className="mt-6">
            <SearchBar big onSubmit={(q) => router.push(`/search?q=${encodeURIComponent(q)}`)} />
            <ul aria-label="Suggestions" className="mt-3 flex flex-wrap gap-2">
              {SUGGESTIONS.map((label) => (
                <li key={label}>
                  <button type="button" className="chip transition hover:border-accent/70 hover:text-accent" onClick={() => pick(label)}>{label}</button>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </motion.div>
      <div className="absolute inset-x-0 bottom-3 z-20 flex flex-wrap items-end justify-between gap-2 px-3 sm:px-5 lg:left-[46%] lg:right-3">
        <div className="flex min-w-0 flex-col gap-2">
          <label className="glass inline-flex w-fit cursor-pointer items-center gap-2 px-3 py-2 text-sm text-mist">
            <input type="checkbox" checked={showGaps} onChange={(e) => setShowGaps(e.target.checked)} className="accent-gap" />
            Highlight gaps
            <span className="chip inline-block min-w-[2.5ch] text-center tabular-nums" aria-hidden={!gaps.data}>{gaps.data ? gaps.data.length : "\u00a0"}</span>
          </label>
          {/* Fixed-height slot so the controls never jump when clusters arrive. */}
          <div data-testid="legend-slot" className="h-14 w-[min(36rem,calc(100vw-1.5rem))] max-w-xl">
          {clusterLegend.length > 0 && (
            <ul aria-label="Topic clusters" className="glass flex h-full flex-wrap content-start gap-x-3 gap-y-1 overflow-y-auto px-3 py-2 text-xs text-mist">
              {clusterLegend.map((row) => (
                <li key={row.name}>
                  <button type="button" className="inline-flex items-center gap-1.5 rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-accent" onClick={() => setClusterQuery(row.name)}>
                    <span aria-hidden className="inline-block h-2 w-2 rounded-full" style={{ background: row.color }} />
                    {row.name}
                  </button>
                </li>
              ))}
            </ul>
          )}
          </div>
        </div>
        <details className="glass max-h-40 overflow-auto px-3 py-2 text-sm text-mist">
          <summary className="cursor-pointer text-white" title="Each point is a research topic; gaps are topic pairs our sample rarely connects">Topics ({stars.length}){stars.some((n) => n.gap) ? <span className="text-mist"> · {stars.filter((n) => !n.gap).length} topics + {stars.filter((n) => n.gap).length} gaps</span> : null}</summary>
          <ul className="mt-2 max-h-28 space-y-1 overflow-auto">
            {stars.map((n) => (
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
    <div role="status" className="flex h-full flex-col items-center justify-center gap-4 text-sm text-mist">
      <StarMark />
      <div className="flex items-center gap-2"><Spinner /> Placing papers</div>
    </div>
  );
}
