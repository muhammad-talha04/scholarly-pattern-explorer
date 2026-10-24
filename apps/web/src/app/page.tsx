import type { Metadata } from "next";
import { pageMeta } from "@/lib/seo";
import { GalaxyHero } from "@/features/galaxy/GalaxyHero";
export default function Home() { return <GalaxyHero />; }

export const metadata: Metadata = { ...pageMeta("/", "Scholarly Pattern Explorer: a map of computer science research", "Search computer science papers by meaning, and explore a galaxy of papers, emerging patterns and research gaps in about 100,000 OpenAlex papers."), title: { absolute: "Scholarly Pattern Explorer: a map of computer science research" } };
