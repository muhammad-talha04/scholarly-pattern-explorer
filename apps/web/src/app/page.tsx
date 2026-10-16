import type { Metadata } from "next";
import { pageMeta } from "@/lib/seo";
import { GalaxyHero } from "@/features/galaxy/GalaxyHero";
export default function Home() { return <GalaxyHero />; }

export const metadata: Metadata = { ...pageMeta("/", "Scholarly Pattern Explorer: a map of recent AI research", "Explore about 14,000 recent AI papers from OpenAlex as a galaxy of topics, with emerging patterns and research gaps."), title: { absolute: "Scholarly Pattern Explorer: a map of recent AI research" } };
