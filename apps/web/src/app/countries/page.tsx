import { pageMeta } from "@/lib/seo";
import { CountriesPage } from "@/features/countries/CountriesPage";
import { prefetch } from "@/lib/api/server";
import type { CountryStats } from "@/lib/api/types";

export const revalidate = 3600;

export default async function Page() {
  const initial = await prefetch<CountryStats[]>("/countries?counting=fractional");
  return <CountriesPage initialCountries={Array.isArray(initial) ? initial : undefined} />;
}

export const metadata = pageMeta("/countries", "AI research by country and region", "Paper counts and co-authorship arcs for countries and regions in a two-year sample of AI papers from OpenAlex.");
