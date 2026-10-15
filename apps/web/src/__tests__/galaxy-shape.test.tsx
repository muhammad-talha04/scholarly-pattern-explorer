import { render, screen } from "@testing-library/react";
import { vi } from "vitest";
import { normalizeGalaxy } from "@/lib/api/client";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/features/galaxy/Galaxy3D", () => ({ default: () => <div data-testid="galaxy-canvas" /> }));

const FLAT = [
  { id: "W9", x: 1, y: 0, z: -1, cluster_id: 2, cluster_label: "quark lattices", year: 2024 },
];

vi.mock("@/lib/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
  return {
    ...actual,
    prefersFixtures: () => false,
    api: {
      patterns: () => Promise.resolve({ data: [], source: "live" }),
      galaxy: () => Promise.resolve({ data: actual.normalizeGalaxy(FLAT), source: "live" }),
    },
  };
});

it("renders a flat galaxy list as nodes instead of crashing", async () => {
  const { GalaxyHero } = await import("@/features/galaxy/GalaxyHero");
  render(<GalaxyHero />);
  expect(await screen.findByText("W9")).toBeInTheDocument();
  expect(screen.queryByTestId("galaxy-empty")).not.toBeInTheDocument();
  expect(normalizeGalaxy(FLAT).clusters).toEqual([{ id: "2", name: "quark lattices" }]);
});
