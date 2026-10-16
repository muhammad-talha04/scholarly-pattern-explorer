import { pageMeta } from "@/lib/seo";
import { Suspense } from "react";
import { SearchPage } from "@/features/search/SearchPage";
export default function Page() { return <Suspense><SearchPage /></Suspense>; }

export const metadata = pageMeta("/search", "Search AI papers", "Search AI research papers by keyword and topic, filtered by country and year. Meaning-based search is being upgraded.");
