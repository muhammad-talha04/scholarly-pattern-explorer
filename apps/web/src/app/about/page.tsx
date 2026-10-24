import Link from "next/link";
import { pageMeta } from "@/lib/seo";

export const metadata = pageMeta("/about", "About the data", "What this explorer covers: about 100,000 computer science papers from OpenAlex, 2015 to 2026, sampled evenly by month, and the limits of that sample.");

const FACTS: [string, string][] = [
  ["Source", "OpenAlex, field 17 (Computer Science), articles with an abstract of at least 200 characters"],
  ["Published", "January 2015 to October 2026, drawn evenly from every month"],
  ["Papers", "About 100,000"],
  ["Largest share", "China and the United States"],
];

export default function AboutPage() {
  return (
    <article className="mx-auto max-w-3xl space-y-8 py-6 text-mist">
      <header>
        <h1 className="font-display text-3xl text-white sm:text-4xl">About the data</h1>
        <p className="mt-3 text-lg">This explorer is built on a <strong className="text-white">sample</strong> of computer science research, not on all of it. Read every chart as &ldquo;in this sample&rdquo;.</p>
      </header>
      <dl className="glass grid gap-x-6 gap-y-3 p-5 sm:grid-cols-[10rem_1fr]">
        {FACTS.map(([k, v]) => (<div key={k} className="contents"><dt className="text-xs uppercase tracking-wide text-slate-400">{k}</dt><dd className="text-white">{v}</dd></div>))}
      </dl>
      <section className="space-y-3">
        <h2 className="text-xl font-semibold text-white">What the sample does and does not cover</h2>
        <ul className="list-disc space-y-2 pl-5">
          <li>Only papers OpenAlex files under Computer Science. Computer science work filed under other fields (medicine, physics, linguistics) is mostly missing, and some papers OpenAlex labels as computer science carry topics from other fields.</li>
          <li>Each month contributes a similar number of papers, so a raw count is flat by design. The Progress page shows the estimated real output per year.</li>
          <li>Country shares follow author affiliations in OpenAlex. Recent papers have fewer affiliations recorded, so the newest months under-count some countries.</li>
          <li>Hong Kong, Macao, Taiwan, Réunion and similar territories are shown as regions, as OpenAlex lists them separately.</li>
        </ul>
      </section>
      <section className="space-y-3">
        <h2 className="text-xl font-semibold text-white">What a &ldquo;gap&rdquo; means</h2>
        <p>A research gap here is a topic that grew fast but still has few papers <em>in this sample</em>, or a pair of topics that rarely appear together. It is not proof that nobody in the world works on it. Papers outside this sample can easily fill it.</p>
      </section>
      <section className="space-y-3">
        <h2 className="text-xl font-semibold text-white">Reading the galaxy</h2>
        <p>Each dot is a paper and nearby papers have similar meaning. The galaxy shows a sample of papers chosen to represent every cluster; clusters are named after their most distinctive topics.</p>
      </section>
      <section className="space-y-3">
        <h2 className="text-xl font-semibold text-white">Growth figures</h2>
        <p>Growth trends are hidden for now: only about 72% of 2026 papers have author countries recorded, against 97% of 2025 papers, so a year-to-date comparison would show false declines. When they return, growth compares two periods of equal length. When either period has fewer than 30 papers, it will show &ldquo;Not enough data&rdquo; instead of a percentage, because small counts swing wildly.</p>
      </section>
      <section className="space-y-3">
        <h2 className="text-xl font-semibold text-white">How search works today</h2>
        <p>Search and the galaxy layout use the BAAI bge-small sentence-embedding model (384 dimensions), so papers are matched by meaning, not only by shared words. Results below a similarity floor are dropped, so an off-topic query returns no match rather than a weak one.</p>
      </section>
      <p><Link href="/" className="text-accent hover:underline">Back to the galaxy</Link></p>
    </article>
  );
}
