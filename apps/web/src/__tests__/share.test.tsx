import { render, screen } from "@testing-library/react";
import { Share, shareBlocked } from "@/features/countries/Share";
import { SHOW_SHARE } from "@/lib/flags";

test("share column is off by default", () => expect(SHOW_SHARE).toBe(false));

test("shows share and pp change with tooltip details", () => {
  render(<Share c={{ share_pct: 31.24, share_prev_pct: 28.0, share_change_pp: 3.24, growth_cur_count: 4000, growth_prev_count: 3500, growth_window_start: "2026-01-01", growth_window_end: "2026-09-30" }} />);
  const el = screen.getByText("31.24%");
  expect(screen.getByText("+3.24 pp")).toBeInTheDocument();
  expect(el.getAttribute("title")).toMatch(/2026-01-01 to 2026-09-30.*Share 31\.24% now vs 28\.00% before.*4,000 papers now vs 3,500/);
});

test("negative change uses a minus sign", () => {
  render(<Share c={{ share_pct: 5, share_change_pp: -1.25 }} />);
  expect(screen.getByText("\u22121.25 pp")).toBeInTheDocument();
});

test("share_reason and the 30-paper rule block the value", () => {
  expect(shareBlocked({ share_pct: 2, share_reason: "too_few_papers" })).toBe("Not enough data (fewer than 30 papers)");
  expect(shareBlocked({ share_pct: 2, share_reason: "partial_year" })).toBe("Not enough data (partial year)");
  expect(shareBlocked({ share_pct: 2, growth_cur_count: 29, growth_prev_count: 100 })).toBe("Not enough data (fewer than 30 papers)");
  expect(shareBlocked({})).toBe("Not enough data");
  expect(shareBlocked({ share_pct: 2, growth_reason: "partial_year" } as never)).toBeNull();
});
