import { render, screen } from "@testing-library/react";
import { vi } from "vitest";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/features/galaxy/Galaxy3D", () => ({ default: () => <div data-testid="galaxy-canvas" /> }));
vi.mock("@/lib/api/client", () => ({
  prefersFixtures: () => false,
  api: {
    patterns: () => Promise.resolve({ data: [], source: "live" }),
    galaxy: () => Promise.resolve({
      data: [{ id: "W1", x: 1, y: 2, z: 3, cluster_id: 0, cluster_label: "protein", year: 2020 }],
      source: "live",
    }),
  },
}));

it("an un-normalized galaxy list shows the empty state instead of throwing", async () => {
  const { GalaxyHero } = await import("@/features/galaxy/GalaxyHero");
  render(<GalaxyHero />);
  expect(await screen.findByTestId("galaxy-empty")).toHaveTextContent(/No topics in this snapshot/);
});
