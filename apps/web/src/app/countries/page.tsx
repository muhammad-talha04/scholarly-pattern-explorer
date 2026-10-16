import { pageMeta } from "@/lib/seo";
import { CountriesPage } from "@/features/countries/CountriesPage";
export default function Page() { return <CountriesPage />; }

export const metadata = pageMeta("/countries", "AI research by country and region", "Paper counts, equal-period growth and co-authorship arcs for countries and regions in a two-year sample of AI papers from OpenAlex.");
