import Link from "next/link";
import { pageMeta } from "@/lib/seo";

export const metadata = pageMeta("/about", "About the data", "What this explorer covers: 14,159 AI papers from OpenAlex (subfield 1702) published since 15 Oct 2024, and the limits of that sample.");

const FACTS: [string, string][] = [
  ["Source", "OpenAlex, subfield 1702 (Artificial Intelligence), articles only"],
  ["Published", "On or after 15 October 2024, about a two-year window"],
  ["Papers", "14,159"],
  ["Largest share", "China, about 31% of papers"],
];

export default function AboutPage() {
  return (
    <article className="mx-auto max-w-3xl space-y-8 py-6 text-mist">
      <header>
        <h1 className="font-display text-3xl text-white sm:text-4xl">About the data</h1>
        <p className="mt-3 text-lg">This explorer is built on a <strong className="text-white">sample</strong> of recent AI research, not on all of it. Read every chart as &ldquo;in this sample&rdquo;.</p>
      </header>
      <dl className="glass grid gap-x-6 gap-y-3 p-5 sm:grid-cols-[10rem_1fr]">
        {FACTS.map(([k, v]) => (<div key={k} className="contents"><dt className="text-xs uppercase tracking-wide text-slate-400">{k}</dt><dd className="text-white">{v}</dd></div>))}
      </dl>
      <section className="space-y-3">
        <h2 className="text-xl font-semibold text-white">What the sample does and does not cover</h2>
        <ul className="list-disc space-y-2 pl-5">
          <li>Only papers OpenAlex tags with the AI subfield 1702. AI work filed under other fields (medicine, robotics, linguistics) is mostly missing.</li>
          <li>Only about two years of publications, so long-term trends are out of scope.</li>
          <li>Country shares follow author affiliations in OpenAlex. China makes up about 31% of the sample, which shapes every country comparison.</li>
          <li>Hong Kong, Macao, Taiwan, Réunion and similar territories are shown as regions, as OpenAlex lists them separately.</li>
        </ul>
      </section>
      <section className="space-y-3">
        <h2 className="text-xl font-semibold text-white">What a &ldquo;gap&rdquo; means</h2>
        <p>A research gap here is a topic pair that rarely appears together <em>in this sample</em>. It is not proof that nobody in the world works on it. Papers outside subfield 1702 or outside the date window can easily fill it.</p>
      </section>
      <section className="space-y-3">
        <h2 className="text-xl font-semibold text-white">Reading the galaxy</h2>
        <p>Dot positions show topic clusters; connecting lines are decorative. The lines on the home page are drawn for looks and do not mean two topics are related.</p>
      </section>
      <section className="space-y-3">
        <h2 className="text-xl font-semibold text-white">Growth figures</h2>
        <p>Growth trends are hidden while we rebalance the paper sample. When they return, growth will compare two periods of equal length. When either period has fewer than 30 papers, it will show &ldquo;Not enough data&rdquo; instead of a percentage, because small counts swing wildly.</p>
      </section>
      <section className="space-y-3">
        <h2 className="text-xl font-semibold text-white">How search works today</h2>
        <p>Search and the galaxy layout currently use simple 384-dimension hash embeddings. They match shared words and fragments rather than true meaning, so related papers that use different wording can be missed. Meaning-based search is being upgraded to a proper sentence-embedding model; until then, treat search as keyword and topic matching.</p>
      </section>
      <p><Link href="/" className="text-accent hover:underline">Back to the galaxy</Link></p>
    </article>
  );
}
