import { pageMeta } from "@/lib/seo";
import { TimelinePage } from "@/features/timeline/TimelinePage";
import type { ChartScale } from "@/lib/api/types";

export default function Page({ searchParams }: { searchParams?: { corpus?: string; year?: string } }) {
  const scale: ChartScale = searchParams?.corpus === "80k" ? "80k" : "sample";
  const y = Number(searchParams?.year);
  const initialYear = Number.isInteger(y) ? y : null;
  return <TimelinePage scale={scale} initialYear={initialYear} />;
}

export const metadata = pageMeta("/timeline", "Topic progress over time", "How computer science topics rise and fall over time in a 2015 to 2026 OpenAlex sample.");
