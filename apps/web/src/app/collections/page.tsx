import { pageMeta } from "@/lib/seo";
import { CollectionsPage } from "@/features/collections/CollectionsPage";
export default function Page() { return <CollectionsPage />; }

export const metadata = pageMeta("/collections", "Your saved papers", "Papers you saved while exploring. Stored only in this browser.", { noindex: true });
