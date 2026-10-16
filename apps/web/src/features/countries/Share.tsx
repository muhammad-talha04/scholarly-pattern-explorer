import type { CountryStats, GrowthReason } from "@/lib/api/types";

export const MIN_PAPERS = 30;

const REASON_TEXT: Record<GrowthReason, string> = {
  too_few_papers: "Not enough data (fewer than 30 papers)",
  partial_year: "Not enough data (partial year)",
};

type ShareFields = Pick<Partial<CountryStats>,
  "share_pct" | "share_prev_pct" | "share_change_pp" | "share_reason" |
  "growth_cur_count" | "growth_prev_count" | "growth_window_start" | "growth_window_end">;

const pct = (v: number) => `${v.toFixed(2)}%`;

/** Tooltip: both shares, both counts and the window dates when the API sends them. */
export function shareDetail(c: ShareFields): string {
  const parts: string[] = [];
  if (c.growth_window_start && c.growth_window_end) parts.push(`Current window ${c.growth_window_start} to ${c.growth_window_end}, vs the same dates one year earlier`);
  if (c.share_pct != null && c.share_prev_pct != null) parts.push(`Share ${pct(c.share_pct)} now vs ${pct(c.share_prev_pct)} before`);
  if (c.growth_cur_count != null && c.growth_prev_count != null) parts.push(`${Math.round(c.growth_cur_count).toLocaleString()} papers now vs ${Math.round(c.growth_prev_count).toLocaleString()} before`);
  parts.push(`Both periods need at least ${MIN_PAPERS} papers`);
  return parts.join(". ") + ".";
}

/** Reason the share can't be shown, or null. The backend's share_reason wins; counts under 30 are a client-side backstop. */
export function shareBlocked(c: ShareFields): string | null {
  if (c.share_reason && c.share_reason in REASON_TEXT) return REASON_TEXT[c.share_reason];
  if ((c.growth_cur_count != null && c.growth_cur_count < MIN_PAPERS) || (c.growth_prev_count != null && c.growth_prev_count < MIN_PAPERS)) return REASON_TEXT.too_few_papers;
  if (c.share_pct == null || !Number.isFinite(c.share_pct)) return "Not enough data";
  return null;
}

export function Share({ c }: { c: ShareFields }) {
  const detail = shareDetail(c);
  const blocked = shareBlocked(c);
  if (blocked) return <span className="text-slate-400" title={detail}>{blocked}</span>;
  const d = c.share_change_pp;
  return (
    <span title={detail} className="tabular-nums">
      {pct(c.share_pct!)}
      {d != null && Number.isFinite(d) && (
        <span className={`block text-[10px] ${d >= 0 ? "text-up" : "text-down"}`}>{d >= 0 ? "+" : "\u2212"}{Math.abs(d).toFixed(2)} pp</span>
      )}
    </span>
  );
}
