import { pageMeta } from "@/lib/seo";
import { TimelinePage } from "@/features/timeline/TimelinePage";
export default function Page() { return <TimelinePage />; }

export const metadata = pageMeta("/timeline", "Topic progress over time", "How AI research topics rise and fall over time in a two-year OpenAlex sample.");
