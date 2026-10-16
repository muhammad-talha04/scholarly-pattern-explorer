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
