import type { Metadata } from "next";
import { pageMeta } from "@/lib/seo";
import { GalaxyHero, HERO_GALAXY_LIMIT } from "@/features/galaxy/GalaxyHero";
import { normalizeGalaxy } from "@/lib/api/client";
import { prefetch } from "@/lib/api/server";
import type { Pattern } from "@/lib/api/types";

// Rebuilt in the background every 10 minutes. Visitors get the cached page and data, so the
// free API waking up from sleep never blocks a first visit.
export const revalidate = 600;
const list = (x: unknown) => (Array.isArray(x) ? (x as Pattern[]) : undefined);

export default async function Home() {
  const [pats, gaps, galaxy] = await Promise.all([
    prefetch<Pattern[]>("/patterns"),
    prefetch<Pattern[]>("/patterns?trend=gap"),
    prefetch<unknown>(`/galaxy?limit=${HERO_GALAXY_LIMIT}`),
  ]);
  return <GalaxyHero initial={{ pats: list(pats), gaps: list(gaps), galaxy: galaxy ? normalizeGalaxy(galaxy) : undefined }} />;
}

export const metadata: Metadata = { ...pageMeta("/", "Scholarly Pattern Explorer: a map of computer science research", "Search computer science papers by meaning, and explore a galaxy of papers, emerging patterns and research gaps in about 100,000 OpenAlex papers."), title: { absolute: "Scholarly Pattern Explorer: a map of computer science research" } };
