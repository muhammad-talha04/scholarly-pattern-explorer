import { pageMeta } from "@/lib/seo";
import { CountriesPage } from "@/features/countries/CountriesPage";
import type { ChartScale } from "@/lib/api/types";

export default function Page({ searchParams }: { searchParams?: { corpus?: string } }) {
  const scale: ChartScale = searchParams?.corpus === "80k" ? "80k" : "sample";
  return <CountriesPage scale={scale} />;
}

export const metadata = pageMeta("/countries", "AI research by country and region", "Paper counts and co-authorship arcs for countries and regions in a two-year sample of AI papers from OpenAlex.");
