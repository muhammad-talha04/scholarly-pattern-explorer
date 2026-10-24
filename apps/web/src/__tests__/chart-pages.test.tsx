import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";

const calls = vi.hoisted(() => ({ topicCountryYears: 0, publications: 0 }));

vi.mock("next/dynamic", () => ({ default: () => function GlobeStub() { return <div data-testid="globe-stub" />; } }));

vi.mock("@/lib/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
  return {
    prefersFixtures: () => true,
    api: {
      ...actual.api,
      publications: (q: Parameters<typeof actual.api.publications>[0]) => {
        calls.publications += 1;
        return actual.api.publications(q);
      },
      topicCountryYears: () => {
        calls.topicCountryYears += 1;
        return Promise.resolve({ data: [], source: "mock" as const });
      },
    },
  };
});

it("timeline reads the publication aggregate and does not count topic rows", async () => {
  const { TimelinePage } = await import("@/features/timeline/TimelinePage");
  render(<TimelinePage scale="80k" />);
  expect(await screen.findByTestId("publication-chart")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Estimated OpenAlex output" })).toBeInTheDocument();
  expect(screen.getByText(/80,000 sampled/)).toBeInTheDocument();
  expect(calls.topicCountryYears).toBe(0);
  expect(calls.publications).toBeGreaterThan(0);
  fireEvent.click(screen.getByRole("button", { name: /2015: Estimated OpenAlex output/ }));
  expect(await screen.findByText(/Empty months stay on the axis/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "All years" })).toBeInTheDocument();
  expect(calls.topicCountryYears).toBe(0);
});

it("country page charts the top 12 plus Other from precomputed totals", async () => {
  const { CountriesPage } = await import("@/features/countries/CountriesPage");
  render(<CountriesPage scale="80k" />);
  expect(await screen.findByTestId("country-other")).toBeInTheDocument();
  const chart = screen.getByTestId("country-chart");
  expect(chart.querySelectorAll("li")).toHaveLength(13);
  expect(chart).not.toHaveTextContent("Hungary");
  expect(calls.topicCountryYears).toBe(0);
});
