/** Deterministic fixtures shaped exactly like apps/api/app/schemas.py. */
import type { AskResponse, Collaboration, Counting, CountryStats, PaperDetail, PaperSummary, Pattern, Run, SearchParams, SearchResponse } from "./types";

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

const PAPERS: PaperDetail[] = Array.from({ length: 24 }, (_, i) => {
  const r = rng(i + 7);
  const t1 = TOPICS[i % TOPICS.length], t2 = TOPICS[(i * 5 + 3) % TOPICS.length];
  const c = [COUNTRY_META[i % COUNTRY_META.length][0], COUNTRY_META[(i * 3 + 1) % COUNTRY_META.length][0]];
  const id = `W${4100000000 + i * 7919}`;
  return {
    id,
    title: `${t1} meets ${t2.toLowerCase()}: ${["a survey", "new benchmarks", "scaling laws", "a causal view", "lessons from deployment", "an open dataset"][i % 6]}`,
    authors: [["A. Khan", "L. Chen", "M. Rossi"], ["S. Patel", "J. Müller"], ["E. Okafor", "Y. Tanaka", "R. Silva", "K. Lee"]][i % 3],
    year: 2018 + (i % 9),
    cited_by: Math.floor(r() * 900),
    one_line_summary: `Shows how ${t1.toLowerCase()} improves ${t2.toLowerCase()} on standard benchmarks.`,
    score: null,
    abstract: `We study ${t1.toLowerCase()} in the context of ${t2.toLowerCase()}. Using a dataset of ${Math.floor(r() * 90 + 10)}k samples we find consistent gains and release code.`,
    summary: `This paper connects ${t1.toLowerCase()} with ${t2.toLowerCase()}. The authors propose a method, evaluate it against strong baselines, and report a ${Math.floor(r() * 20 + 3)}% improvement. Limitations include dataset bias and compute cost.`,
    topics: [t1, t2],
    countries: c,
    original_url: `https://doi.org/10.1234/spe.${i}`,
    openalex_url: `https://openalex.org/${id}`,
  };
});

const toSummary = ({ id, title, authors, year, cited_by, one_line_summary, score }: PaperDetail): PaperSummary =>
  ({ id, title, authors, year, cited_by, one_line_summary, score });

export function search(p: SearchParams): SearchResponse {
  const words = p.q.toLowerCase().split(/\s+/).filter(Boolean);
  const results = PAPERS
    .filter((x) => (!p.country || x.countries.includes(p.country)) && (!p.year_from || (x.year ?? 0) >= p.year_from))
    .map((x) => {
      const hay = `${x.title} ${x.abstract} ${x.topics.join(" ")}`.toLowerCase();
      const hits = words.filter((w) => hay.includes(w)).length;
      return { ...toSummary(x), score: Math.round((0.35 + 0.6 * (words.length ? hits / words.length : 0.5)) * 1000) / 1000 };
    })
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
    .slice(0, p.limit ?? 20);
  return { query: p.q, results };
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
export function patterns(window?: number): Pattern[] {
  const out: Pattern[] = [];
  for (let w = 2019; w <= 2025; w += 2) {
    TOPICS.forEach((t, i) => {
      const r = rng(i * 31 + w);
      out.push({ items: [t], support: Math.round((0.05 + r() * 0.3) * 1000) / 1000, window_start: w, window_end: w + 1 });
      if (i % 2 === 0) out.push({ items: [t, TOPICS[(i + 3) % TOPICS.length]], support: Math.round((0.02 + r() * 0.12) * 1000) / 1000, window_start: w, window_end: w + 1 });
      if (i % 4 === 0 && w >= 2021) out.push({ items: [t, TOPICS[(i + 1) % TOPICS.length], TOPICS[(i + 6) % TOPICS.length]], support: Math.round((0.01 + r() * 0.05) * 1000) / 1000, window_start: w, window_end: w + 1 });
    });
  }
  return window === undefined ? out : out.filter((p) => p.window_start === window);
}
export function gaps(): Pattern[] {
  return ["Federated learning", "Edge computing", "Protein folding", "Energy systems"].map((t, i) => ({
    items: [t], support: 0.82 - i * 0.13, window_start: 2023, window_end: 2025,
    gap_score: 0.82 - i * 0.13, growth_rate: 0.6 - i * 0.1, paper_count: 40 + i * 12,
    top_countries: [["PK", "IN", "NG"], ["CN", "KR"], ["US", "GB"], ["DE", "SA"]][i],
  }));
}
export function countries(counting: Counting = "fractional"): CountryStats[] {
  return COUNTRY_META.map(([code, name, papers, growth], i) => ({
    code, name, papers: counting === "full" ? Math.round(papers * 1.38) : papers,
    growth_pct: growth, top_topics: [TOPICS[i % TOPICS.length], TOPICS[(i + 4) % TOPICS.length], TOPICS[(i + 9) % TOPICS.length]],
  }));
}
export function country(code: string): CountryStats { return countries().find((c) => c.code === code) ?? { code, name: code, papers: 0, growth_pct: null, top_topics: [] }; }
export function collaborations(): Collaboration[] {
  return [["US", "CN", 420], ["US", "GB", 310], ["US", "CA", 280], ["DE", "FR", 190], ["CN", "SG", 150], ["GB", "IN", 120],
    ["PK", "CN", 95], ["PK", "SA", 60], ["JP", "US", 140], ["AU", "CN", 130], ["BR", "US", 80], ["NG", "GB", 45], ["ZA", "GB", 50], ["KR", "US", 110], ["NL", "DE", 90]]
    .map(([source, target, papers]) => ({ source: source as string, target: target as string, papers: papers as number }));
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
