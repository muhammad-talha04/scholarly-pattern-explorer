import type { Metadata } from "next";
import { pageMeta } from "@/lib/seo";
import { GalaxyHero } from "@/features/galaxy/GalaxyHero";
export default function Home() { return <GalaxyHero />; }

export const metadata: Metadata = { ...pageMeta("/", "Scholarly Pattern Explorer: a map of recent AI research", "Search AI research papers by keyword and topic, and explore a galaxy of topics, emerging patterns and research gaps in about 14,000 recent OpenAlex papers."), title: { absolute: "Scholarly Pattern Explorer: a map of recent AI research" } };
