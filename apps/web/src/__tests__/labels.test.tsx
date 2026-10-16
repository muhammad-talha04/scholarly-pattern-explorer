import { render, screen } from "@testing-library/react";
import { Growth } from "@/features/countries/CountriesPage";
import { isRegion } from "@/lib/regions";

test("growth shows Not enough data for null", () => {
  render(<><Growth v={null} /><Growth v={12.34} /></>);
  expect(screen.getByText("Not enough data")).toBeInTheDocument();
  expect(screen.getByText("+12.3%")).toBeInTheDocument();
});

test("regions are flagged, sovereign countries are not", () => {
  expect(isRegion("HK")).toBe(true);
  expect(isRegion("tw")).toBe(true);
  expect(isRegion("RE")).toBe(true);
  expect(isRegion("CN")).toBe(false);
});

test("growth uses reason, counts and window when present", () => {
  const c = { growth_reason: "too_few_papers" as const, growth_cur_count: 12, growth_prev_count: 40, growth_window_start: "2026-01-01", growth_window_end: "2026-09-30" };
  render(<><Growth v={null} c={c} /><Growth v={null} c={{ growth_reason: "partial_year" }} /><Growth v={25} c={{ ...c, growth_reason: null, growth_cur_count: 50 }} /></>);
  const a = screen.getByText("Not enough data (fewer than 30 papers)");
  expect(a.getAttribute("title")).toMatch(/2026-01-01 to 2026-09-30.*12 papers now vs 40/);
  expect(screen.getByText("Not enough data (partial year)")).toBeInTheDocument();
  expect(screen.getByText("50 vs 40")).toBeInTheDocument();
});

test("growth is hidden by default with a note", async () => {
  const { SHOW_GROWTH } = await import("@/lib/flags");
  expect(SHOW_GROWTH).toBe(false);
  const { GrowthHiddenNote } = await import("@/features/countries/CountriesPage");
  render(<GrowthHiddenNote />);
  expect(screen.getByTestId("growth-hidden")).toHaveTextContent("Growth trends are hidden while we rebalance the paper sample; see About the data.");
  expect(screen.getByRole("link", { name: "About the data" })).toHaveAttribute("href", "/about");
});
