import type { Pattern } from "./api/types";
export interface TopicNode { id: string; support: number; gap: boolean; gapScore?: number; cluster?: string }
export interface TopicLink { source: string; target: string; weight: number }
/** Topics = distinct items, sized by summed support of their single-item patterns; links = co-occurrence in multi-item patterns. */
export function buildTopicGraph(patterns: Pattern[], gaps: Pattern[] = []) {
  const support = new Map<string, number>(), links = new Map<string, TopicLink>();
  for (const p of patterns) {
    for (const it of p.items) support.set(it, (support.get(it) ?? 0) + (p.items.length === 1 ? p.support : p.support / 4));
    for (let i = 0; i < p.items.length; i++) for (let j = i + 1; j < p.items.length; j++) {
      const [a, b] = [p.items[i], p.items[j]].sort(), k = `${a}|${b}`;
      const l = links.get(k) ?? { source: a, target: b, weight: 0 };
      l.weight += p.support; links.set(k, l);
    }
  }
  const gapMap = new Map(gaps.map((g) => [g.items[0], g.gap_score ?? g.support]));
  for (const g of gapMap.keys()) if (!support.has(g)) support.set(g, 0.05);
  const nodes: TopicNode[] = [...support].map(([id, s]) => ({ id, support: s, gap: gapMap.has(id), gapScore: gapMap.get(id) }));
  return { nodes: nodes.sort((a, b) => b.support - a.support), links: [...links.values()] };
}
/** Pattern lifecycles: for each itemset, which windows it appears in, plus born/died windows. */
export function lifecycles(patterns: Pattern[]) {
  const windows = [...new Set(patterns.map((p) => p.window_start))].sort((a, b) => a - b);
  const by = new Map<string, Map<number, number>>();
  for (const p of patterns) { const k = p.items.join(" + "); if (!by.has(k)) by.set(k, new Map()); by.get(k)!.set(p.window_start, p.support); }
  return { windows, rows: [...by].map(([key, m]) => {
    const present = windows.filter((w) => m.has(w));
    const born = present[0], last = present[present.length - 1];
    return { key, supports: windows.map((w) => m.get(w) ?? null), born, died: last !== windows[windows.length - 1] ? windows[windows.indexOf(last) + 1] : null };
  }) };
}

export interface BornDied {
  win: number | null;
  matched: number | null;
  born: { key: string }[];
  died: { key: string }[];
  /** matched: the run year lines up with a window that changed. fallback: an earlier window did. stable: nothing is born or dies. */
  note: "matched" | "fallback" | "stable" | "no-patterns";
}

/** Born/died itemsets for the pattern window that a timeline year falls in. */
export function selectBornDied(patterns: Pattern[], year: number): BornDied {
  const life = lifecycles(patterns);
  if (!life.windows.length) return { win: null, matched: null, born: [], died: [], note: "no-patterns" };
  const matched = [...life.windows].reverse().find((w) => w <= year) ?? life.windows[life.windows.length - 1];
  const at = (win: number) => ({
    born: life.rows.filter((r) => r.born === win && win !== life.windows[0]),
    died: life.rows.filter((r) => r.died === win),
  });
  const direct = at(matched);
  if (direct.born.length || direct.died.length) return { win: matched, matched, ...direct, note: "matched" };
  const earlier = [...life.windows].reverse().find((w) => { const x = at(w); return x.born.length + x.died.length > 0; });
  if (earlier != null) return { win: earlier, matched, ...at(earlier), note: "fallback" };
  return { win: matched, matched, born: [], died: [], note: "stable" };
}
