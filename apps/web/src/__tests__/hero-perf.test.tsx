import { render, screen } from "@testing-library/react";
import { vi } from "vitest";

const galaxy = vi.fn(() => Promise.resolve({ data: { nodes: [], clusters: [], links: [] }, source: "mock" }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/lib/api/client", () => ({
  prefersFixtures: () => true,
  api: { patterns: () => Promise.resolve({ data: [], source: "mock" }), galaxy },
}));

it("hero asks for a 600-node galaxy and renders its text immediately", async () => {
  const { GalaxyHero, HERO_GALAXY_LIMIT } = await import("@/features/galaxy/GalaxyHero");
  expect(HERO_GALAXY_LIMIT).toBe(600);
  render(<GalaxyHero />);
  expect(galaxy).toHaveBeenCalledWith(600);
  expect(screen.getByRole("heading", { level: 1 })).toBeVisible();
});

it("placeholder fills the canvas box", async () => {
  const { GalaxyPlaceholder } = await import("@/features/galaxy/GalaxyHero");
  render(<GalaxyPlaceholder />);
  expect(screen.getByTestId("galaxy-placeholder").className).toMatch(/absolute inset-0/);
});
