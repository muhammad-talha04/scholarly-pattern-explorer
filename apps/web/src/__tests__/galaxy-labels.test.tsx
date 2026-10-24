import { render, screen } from "@testing-library/react";
import { vi } from "vitest";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/features/galaxy/Galaxy3D", () => ({ default: () => <div data-testid="galaxy-canvas" /> }));

const GRAPH = {
  nodes: [{
    id: "W1",
    title: "Transformers for protein structure",
    topic_id: "protein-folding",
    topic_name: "Protein folding",
    x: 1, y: 0, z: -1,
    cluster_id: "0",
    support: 1,
  }],
  clusters: [{ id: "0", name: "protein, structure" }],
  links: [],
};

vi.mock("@/lib/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
  return {
    ...actual,
    prefersFixtures: () => false,
    api: {
      patterns: () => Promise.resolve({ data: [], source: "live" }),
      galaxy: () => Promise.resolve({ data: actual.normalizeGalaxy(GRAPH), source: "live" }),
    },
  };
});

it("topics list shows the paper title and the OpenAlex topic", async () => {
  const { GalaxyHero } = await import("@/features/galaxy/GalaxyHero");
  render(<GalaxyHero />);
  expect(await screen.findByText("Transformers for protein structure")).toBeInTheDocument();
  expect(screen.getAllByText("Protein folding")).toHaveLength(2);
  expect(screen.getByText("protein, structure")).toBeInTheDocument();
});
