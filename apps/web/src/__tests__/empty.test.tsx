import { render, screen } from "@testing-library/react";
import { vi } from "vitest";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/lib/api/client", () => ({
  prefersFixtures: () => true,
  api: {
    patterns: () => Promise.resolve({ data: [], source: "mock" }),
    galaxy: () => Promise.resolve({ data: { nodes: [], clusters: [], links: [] }, source: "mock" }),
  },
}));

it("empty galaxy is a designed state, not a blank canvas", async () => {
  const { GalaxyHero } = await import("@/features/galaxy/GalaxyHero");
  render(<GalaxyHero />);
  expect(await screen.findByTestId("galaxy-empty")).toHaveTextContent(/No topics in this snapshot/);
  expect(screen.getByRole("link", { name: /Search papers/ })).toBeInTheDocument();
});
