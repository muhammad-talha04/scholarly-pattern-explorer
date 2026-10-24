import { pageMeta } from "@/lib/seo";
import { Suspense } from "react";
import { SearchPage } from "@/features/search/SearchPage";
export default function Page() { return <Suspense><SearchPage /></Suspense>; }

export const metadata = pageMeta("/search", "Search computer science papers", "Search about 100,000 computer science papers by meaning, filtered by country and year.");
