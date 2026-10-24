/** Deterministic fixtures shaped exactly like apps/api/app/schemas.py. */
import { openAlexSearchUrl } from "../paperLink";
import type { AskResponse, ChartScale, Collaboration, Counting, CountryChart, CountryStats, GalaxyGraph, PaperDetail, PaperSummary, Pattern, PublicationAggregate, Run, SearchParams, SearchResponse, TimeGrain, TopicAggregate, TopicCountryYear, TopicYearQuery } from "./types";
import { countryChartFromStats } from "@/lib/charts/aggregate";
import { countriesAtScale, publicationAggregate as publicationAtScale, sampledByYear, topicAggregate as topicAtScale } from "@/lib/charts/scale";
import { distribute } from "@/lib/charts/axis";

export const TOPICS = [
  "Large language models", "Graph neural networks", "Federated learning", "Climate modelling",
  "Protein folding", "Quantum computing", "Explainable AI", "Reinforcement learning",
  "Computer vision", "Drug discovery", "Edge computing", "Privacy", "Robotics", "Energy systems",
];

const COUNTRY_META: [string, string, number, number][] = [
  ["US", "United States", 3200, 4.1], ["CN", "China", 3550, 11.8], ["GB", "United Kingdom", 1180, 3.2],
  ["DE", "Germany", 1040, 2.6], ["IN", "India", 980, 14.3], ["JP", "Japan", 720, 1.1],
  ["CA", "Canada", 690, 5.0], ["FR", "France", 650, 2.2], ["KR", "South Korea", 560, 7.9],
  ["AU", "Australia", 470, 4.4], ["BR", "Brazil", 380, 9.2], ["PK", "Pakistan", 260, 18.6],
  ["IT", "Italy", 450, 1.8], ["NL", "Netherlands", 330, 2.9], ["SG", "Singapore", 210, 6.5],
  ["ZA", "South Africa", 140, 8.1], ["NG", "Nigeria", 90, 21.4], ["SA", "Saudi Arabia", 240, 16.0],
];

function rng(seed: number) { seed = (seed * 9301 + 49297) % 233280 + 1; return () => ((seed = (seed * 16807) % 2147483647) / 2147483647); }

/** Papers past the original 42, spread across the four themes so each cluster stays populated. */
const EXTRA_TOPICS = [
  "Large language models", "Climate modelling", "Edge computing", "Privacy",
  "Graph neural networks", "Protein folding", "Robotics", "Energy systems",
  "Federated learning", "Quantum computing", "Computer vision", "Drug discovery",
  "Explainable AI", "Climate modelling", "Robotics", "Privacy",
  "Reinforcement learning", "Protein folding", "Edge computing", "Energy systems",
  "Computer vision", "Quantum computing", "Robotics", "Privacy",
];
const PAPERS: PaperDetail[] = Array.from({ length: 66 }, (_, i) => {
  const r = rng(i + 7);
  const t1 = i < 42 ? TOPICS[i % TOPICS.length] : EXTRA_TOPICS[i - 42];
  const t2 = TOPICS[(i * 5 + 3) % TOPICS.length];
  const c = [COUNTRY_META[i % COUNTRY_META.length][0], COUNTRY_META[(i * 3 + 1) % COUNTRY_META.length][0]];
  const id = `W${4100000000 + i * 7919}`;
  const title = `${t1} meets ${t2.toLowerCase()}: ${["a survey", "new benchmarks", "scaling laws", "a causal view", "lessons from deployment", "an open dataset"][i % 6]}`;
  // Fixture ids are not OpenAlex works. Both links are a real title search, never a 10.1234 DOI.
  const find = openAlexSearchUrl(title);
  return {
    id,
    title,
    authors: [["A. Khan", "L. Chen", "M. Rossi"], ["S. Patel", "J. Müller"], ["E. Okafor", "Y. Tanaka", "R. Silva", "K. Lee"]][i % 3],
    year: 2018 + (i % 9),
    cited_by: Math.floor(r() * 900),
    one_line_summary: `Shows how ${t1.toLowerCase()} improves ${t2.toLowerCase()} on standard benchmarks.`,
    score: null,
    abstract: `We study ${t1.toLowerCase()} in the context of ${t2.toLowerCase()}. Using a dataset of ${Math.floor(r() * 90 + 10)}k samples we find consistent gains and release code.`,
    summary: `This paper connects ${t1.toLowerCase()} with ${t2.toLowerCase()}. The authors propose a method, evaluate it against strong baselines, and report a ${Math.floor(r() * 20 + 3)}% improvement. Limitations include dataset bias and compute cost.`,
    topics: [t1, t2],
    countries: c,
    original_url: find,
    openalex_url: find,
  };
});

/** Sample corpus size. The live site shows this until NEXT_PUBLIC_API_URL is set. */
export const FIXTURE_COUNT = PAPERS.length;

const toSummary = ({ id, title, authors, year, cited_by, one_line_summary, score }: PaperDetail): PaperSummary =>
  ({ id, title, authors, year, cited_by, one_line_summary, score });

export function search(p: SearchParams): SearchResponse {
  const words = p.q.toLowerCase().split(/\s+/).filter(Boolean);
  const ranked = PAPERS
    .filter((x) => (!p.country || x.countries.includes(p.country)) && (!p.year_from || (x.year ?? 0) >= p.year_from))
    .map((x) => {
      const hay = `${x.title} ${x.abstract} ${x.topics.join(" ")}`.toLowerCase();
      const hits = words.filter((w) => hay.includes(w)).length;
      return { ...toSummary(x), score: Math.round((0.35 + 0.6 * (words.length ? hits / words.length : 0.5)) * 1000) / 1000 };
    })
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
  const limit = Math.max(1, p.limit ?? 20);
  const offset = Math.max(0, p.offset ?? 0);
  return { query: p.q, results: ranked.slice(offset, offset + limit), total: ranked.length, limit, offset };
}
export function paper(id: string): PaperDetail { return PAPERS.find((p) => p.id === id) ?? { ...PAPERS[0], id }; }
export function ask(id: string, q: string): AskResponse {
  const p = paper(id);
  return { answer: `(mock) Based on the abstract: ${p.abstract} Regarding "${q}", the paper's summary notes: ${p.summary}`, sources: [p.abstract ?? ""] };
}
export function related(id: string, limit = 6): PaperSummary[] {
  const p = paper(id);
  return PAPERS.filter((x) => x.id !== id && x.topics.some((t) => p.topics.includes(t))).slice(0, limit).map(toSummary);
}
const WINDOWS = [2019, 2021, 2023, 2025];
/** First two topics fade out after 2023 (they die in the 2025 window). The last two are born in 2025. */
function topicSpan(i: number): [number, number] {
  if (i < 2) return [2019, 2023];
  if (i >= TOPICS.length - 2) return [2025, 2025];
  return [2019, 2025];
}
function active(i: number, w: number) { const [a, b] = topicSpan(i); return w >= a && w <= b; }

export function patterns(window?: number): Pattern[] {
  const out: Pattern[] = [];
  for (const w of WINDOWS) {
    TOPICS.forEach((t, i) => {
      if (!active(i, w)) return;
      const r = rng(i * 31 + w);
      out.push({ items: [t], support: Math.round((0.05 + r() * 0.3) * 1000) / 1000, window_start: w, window_end: w + 1 });
      if (i % 2 === 0 && active((i + 3) % TOPICS.length, w)) {
        out.push({ items: [t, TOPICS[(i + 3) % TOPICS.length]], support: Math.round((0.02 + r() * 0.12) * 1000) / 1000, window_start: w, window_end: w + 1 });
      }
      const j = (i + 1) % TOPICS.length, k = (i + 6) % TOPICS.length;
      if (i % 4 === 0 && w >= 2021 && active(j, w) && active(k, w)) {
        out.push({ items: [t, TOPICS[j], TOPICS[k]], support: Math.round((0.01 + r() * 0.05) * 1000) / 1000, window_start: w, window_end: w + 1 });
      }
    });
  }
  return window === undefined ? out : out.filter((p) => p.window_start === window);
}
export function emerging(): Pattern[] {
  return ["Climate modelling", "Protein folding", "Quantum computing"].map((t, i) => ({
    items: [t], support: 0.7 - i * 0.12, window_start: 2024, window_end: 2026,
    growth_rate: 0.9 - i * 0.2, paper_count: 80 - i * 15,
    top_countries: [["US", "GB"], ["DE", "CH"], ["CN", "JP"]][i],
  }));
}
export function gaps(): Pattern[] {
  return ["Federated learning", "Edge computing", "Protein folding", "Energy systems"].map((t, i) => ({
    items: [t], support: 0.82 - i * 0.13, window_start: 2023, window_end: 2025,
    gap_score: 0.82 - i * 0.13, growth_rate: 0.6 - i * 0.1, paper_count: 40 + i * 12,
    top_countries: [["PK", "IN", "NG"], ["CN", "KR"], ["US", "GB"], ["DE", "SA"]][i],
  }));
}
export function countries(counting: Counting = "fractional", scale: ChartScale = "sample"): CountryStats[] {
  if (scale === "80k") return countriesAtScale(counting);
  const byYear = sampledByYear("sample");
  const years = Object.keys(byYear).map(Number).sort((a, b) => a - b);
  const weights = years.map((year) => byYear[year]);
  return COUNTRY_META.map(([code, name, papers, growth], i) => {
    const full = Math.round(papers * 1.38);
    const fracParts = distribute(papers, weights);
    const fullParts = distribute(full, weights);
    return {
      code, name,
      // per_country changes collaboration weights, not country totals (same as country_api).
      papers: counting === "full" ? full : papers,
      growth_pct: growth, top_topics: [TOPICS[i % TOPICS.length], TOPICS[(i + 4) % TOPICS.length], TOPICS[(i + 9) % TOPICS.length]],
      counting: counting === "full" ? "full" : "fractional",
      paper_count: full,
      fractional_count: papers,
      by_year: years.map((year, yi) => ({ year, paper_count: fullParts[yi], fractional_count: fracParts[yi] })),
    };
  });
}
export function country(code: string, counting: Counting = "fractional"): CountryStats {
  return countries(counting).find((c) => c.code === code) ?? { code, name: code, papers: 0, growth_pct: null, top_topics: [] };
}
const COLLAB_BASE: [string, string, number][] = [["US", "CN", 420], ["US", "GB", 310], ["US", "CA", 280], ["DE", "FR", 190], ["CN", "SG", 150], ["GB", "IN", 120],
  ["PK", "CN", 95], ["PK", "SA", 60], ["JP", "US", 140], ["AU", "CN", 130], ["BR", "US", 80], ["NG", "GB", 45], ["ZA", "GB", 50], ["KR", "US", 110], ["NL", "DE", 90]];
export function collaborations(counting: Counting = "fractional"): Collaboration[] {
  const scale = counting === "full" ? 1 : counting === "per_country" ? 0.5 : 0.34;
  return COLLAB_BASE.map(([source, target, papers]) => ({ source, target, papers: Math.round(papers * scale * 10) / 10 }));
}
function slug(name: string) { return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, ""); }
const THEMES: { id: string; name: string; topics: string[] }[] = [
  { id: "methods", name: "Methods", topics: ["Large language models", "Graph neural networks", "Federated learning", "Explainable AI", "Reinforcement learning", "Computer vision"] },
  { id: "science", name: "Science", topics: ["Climate modelling", "Protein folding", "Quantum computing", "Drug discovery"] },
  { id: "systems", name: "Systems", topics: ["Edge computing", "Robotics"] },
  { id: "society", name: "Society", topics: ["Privacy", "Energy systems"] },
];
function themeFor(topic: string) { return THEMES.find((t) => t.topics.includes(topic)) ?? THEMES[0]; }
/** One dot per fixture paper. The cluster name is the topic group that colors it. */
export function galaxy(limit?: number): GalaxyGraph {
  const golden = Math.PI * (3 - Math.sqrt(5));
  const nodes = PAPERS.map((p, i) => {
    const theme = themeFor(p.topics[0]);
    const r = 6 * Math.sqrt((i + 0.5) / PAPERS.length), a = i * golden;
    return {
      id: p.id, title: p.title,
      topic_id: slug(p.topics[0]), topic_name: p.topics[0],
      x: r * Math.cos(a), y: (((i * 7919) % 13) / 13 - 0.5) * 1.6, z: r * Math.sin(a),
      cluster_id: theme.id, color_index: THEMES.findIndex((t) => t.id === theme.id),
      support: Math.round((0.15 + (p.cited_by % 70) / 100) * 100) / 100,
    };
  });
  const links: GalaxyGraph["links"] = [];
  for (let i = 0; i < nodes.length; i++) {
    const mate = nodes.find((n, j) => j > i && n.cluster_id === nodes[i].cluster_id);
    if (mate && nodes[i].id && mate.id) links.push({ source: nodes[i].id, target: mate.id, weight: 0.4 });
  }
  const clusters = THEMES.map(({ id, name }, i) => ({
    id, name, color_index: i,
    ...(id === "science" ? { emerging_score: 0.72 } : {}),
  }));
  if (limit == null) return { nodes, clusters, links };
  const kept = nodes.slice(0, Math.max(0, limit));
  const names = new Set(kept.map((n) => n.id));
  return { nodes: kept, clusters, links: links.filter((e) => names.has(e.source) && names.has(e.target)) };
}
export function topicCountryYears(q: TopicYearQuery = {}): TopicCountryYear[] {
  const years = [2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026];
  const rows: TopicCountryYear[] = [];
  TOPICS.forEach((name, ti) => {
    const slice = COUNTRY_META.slice(ti % 6, (ti % 6) + 5);
    years.forEach((year, yi) => {
      if (ti < 2 && year > 2023) return;
      if (ti >= TOPICS.length - 2 && year < 2024) return;
      slice.forEach(([code], ci) => {
        const base = 6 + ((ti * 5 + ci * 3 + yi * 2) % 19);
        const trend = 0.55 + yi / 12;
        rows.push({
          topic_id: slug(name), topic_name: name, country_code: code, year,
          paper_count: Math.max(1, Math.round(base * trend)),
          fractional_count: Math.round(base * trend * 0.62 * 10) / 10,
        });
      });
    });
  });
  return rows.filter((r) =>
    (!q.topic_id || r.topic_id === q.topic_id) &&
    (!q.country || r.country_code === q.country.toUpperCase()) &&
    (q.year == null || r.year === q.year)
  ).slice(0, q.limit ?? rows.length);
}
export function publicationAggregate(q: { grain?: TimeGrain; year?: number | null; scale?: ChartScale } = {}): PublicationAggregate {
  return publicationAtScale(q);
}

export function topicVolume(q: { grain?: TimeGrain; year?: number | null; top?: number; scale?: ChartScale } = {}): TopicAggregate {
  return topicAtScale(q);
}

/** Chart payload. Built from the precomputed country totals, not from paper rows. */
export function countryChart(q: { counting?: Counting; top?: number; year?: number | null; scale?: ChartScale } = {}): CountryChart {
  const counting = q.counting ?? "fractional";
  return countryChartFromStats(countries(counting, q.scale ?? "sample"), { top: q.top, year: q.year, counting });
}

export function runs(): Run[] {
  const out: Run[] = [];
  let id = 1;
  for (let m = 0; m < 10; m++) for (const d of [1, 15]) {
    const r = rng(id * 13);
    const start = new Date(Date.UTC(2026, m, d, 2, 0));
    out.push({ id: id++, started_at: start.toISOString(), finished_at: new Date(start.getTime() + 38 * 60000).toISOString(),
      status: id === 8 ? "failed" : "success", papers_added: id === 8 ? 0 : Math.floor(400 + r() * 1600), patterns_changed: Math.floor(r() * 40) });
  }
  return out.filter((r) => new Date(r.started_at) < new Date("2026-10-16"));
}
