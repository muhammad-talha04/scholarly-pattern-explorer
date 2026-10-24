import { pageMeta } from "@/lib/seo";
import { PatternsPage } from "@/features/patterns/PatternsPage";
import { prefetch } from "@/lib/api/server";
import type { Pattern } from "@/lib/api/types";

export const revalidate = 3600;
const list = (x: unknown) => (Array.isArray(x) ? (x as Pattern[]) : undefined);

export default async function Page() {
  const [all, gaps, emerging] = await Promise.all([prefetch<Pattern[]>("/patterns"), prefetch<Pattern[]>("/patterns?trend=gap"), prefetch<Pattern[]>("/patterns?trend=emerging")]);
  return <PatternsPage initial={{ all: list(all), gaps: list(gaps), emerging: list(emerging) }} />;
}

export const metadata = pageMeta("/patterns", "Emerging patterns and research gaps", "Topic combinations that are growing, and topic pairs our sample rarely connects.");
