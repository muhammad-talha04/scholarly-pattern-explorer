import { pageMeta } from "@/lib/seo";
import { CountriesPage } from "@/features/countries/CountriesPage";
import type { ChartScale, CountryStats } from "@/lib/api/types";
import { prefetch } from "@/lib/api/server";

// The prefetch caches for an hour inside fetch(); the page itself reads searchParams, so it renders per request.
export default async function Page({ searchParams }: { searchParams?: { corpus?: string } }) {
  const scale: ChartScale = searchParams?.corpus === "80k" ? "80k" : "sample";
  const initial = await prefetch<CountryStats[]>("/countries?counting=fractional");
  return <CountriesPage scale={scale} initialCountries={Array.isArray(initial) ? initial : undefined} />;
}

export const metadata = pageMeta("/countries", "Computer science research by country and region", "Paper counts and co-authorship arcs for countries and regions in a sample of about 100,000 computer science papers from OpenAlex, 2015 to 2026.");
