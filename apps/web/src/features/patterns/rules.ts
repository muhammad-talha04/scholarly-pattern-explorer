import type { Pattern } from "@/lib/api/types";
export interface Rule { antecedent: string[]; consequent: string[]; support: number; confidence: number; lift: number | null }
/** Derive association rules A → B from frequent itemsets of one window (confidence = s(A∪B)/s(A)). */
export function deriveRules(patterns: Pattern[], minConf = 0): Rule[] {
  const key = (xs: string[]) => [...xs].sort().join("|");
  const s = new Map(patterns.map((p) => [key(p.items), p.support]));
  const out: Rule[] = [];
  for (const p of patterns) {
    if (p.items.length < 2) continue;
    for (const c of p.items) {
      const ante = p.items.filter((x) => x !== c), sa = s.get(key(ante)), sc = s.get(c);
      if (!sa) continue;
      const confidence = p.support / sa;
      if (confidence >= minConf) out.push({ antecedent: ante, consequent: [c], support: p.support, confidence, lift: sc ? confidence / sc : null });
    }
  }
  return out.sort((a, b) => b.confidence - a.confidence);
}
