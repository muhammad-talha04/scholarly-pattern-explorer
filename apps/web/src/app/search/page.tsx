import { pageMeta } from "@/lib/seo";
import { Suspense } from "react";
import { SearchPage } from "@/features/search/SearchPage";
export default function Page() { return <Suspense><SearchPage /></Suspense>; }

export const metadata = pageMeta("/search", "Search AI papers", "Search about 14,000 recent AI papers from OpenAlex and filter by country, topic and year.");
