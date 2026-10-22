import { pageMeta } from "@/lib/seo";
import { Suspense } from "react";
import { ComparePage } from "@/features/compare/ComparePage";
export default function Page() { return <Suspense><ComparePage /></Suspense>; }

export const metadata = pageMeta("/compare", "Compare papers side by side", "Put AI papers next to each other and compare them.", { noindex: true });
