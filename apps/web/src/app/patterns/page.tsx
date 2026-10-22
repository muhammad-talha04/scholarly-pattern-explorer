import { pageMeta } from "@/lib/seo";
import { PatternsPage } from "@/features/patterns/PatternsPage";
export default function Page() { return <PatternsPage />; }

export const metadata = pageMeta("/patterns", "Emerging patterns and research gaps", "Topic combinations that are growing, and topic pairs our sample rarely connects.");
