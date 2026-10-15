import { describe, expect, it, vi, beforeEach } from "vitest";
import { normalizeGalaxy } from "@/lib/api/client";

const GRAPH = {
  nodes: [{ topic_id: "llm", topic_name: "Large language models", x: 1, y: 2, z: 3, cluster_id: "methods", support: 0.4 }],
  clusters: [{ id: "methods", name: "Methods" }],
  links: [{ source: "Large language models", target: "Privacy", weight: 2 }],
};

const FLAT = [
  { id: "W1", x: 0.2, y: -1, z: 4, cluster_id: 0, cluster_label: "protein folding", year: 2020 },
  { id: "W2", x: 1.5, y: 0.5, z: -2, cluster_id: 0, cluster_label: "protein folding", year: 2021 },
  { id: "W3", x: -3, y: 2, z: 1, cluster_id: -1, cluster_label: "", year: null },
  { id: "skip-me", x: "nope", y: 0, z: 0, cluster_id: 1, cluster_label: "bad" },
];

describe("api client fallback", () => {
  beforeEach(() => { vi.resetModules(); vi.unstubAllEnvs(); });
  it("uses mock when NEXT_PUBLIC_API_URL is unset", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "");
    const { api } = await import("@/lib/api/client");
    const r = await api.search({ q: "federated" });
    expect(r.source).toBe("mock");
    expect(r.data.results.length).toBeGreaterThan(0);
  });
  it("falls back to mock on 501 and network error, throws on 404", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://api.test");
    const { request, ApiError } = await import("@/lib/api/client");
    const mk = (status: number) => (async () => new Response("{}", { status })) as unknown as typeof fetch;
    expect((await request("/x", () => 1, undefined, mk(501))).source).toBe("mock");
    expect((await request("/x", () => 1, undefined, (async () => { throw new TypeError("down"); }) as unknown as typeof fetch)).source).toBe("mock");
    await expect(request("/x", () => 1, undefined, mk(404))).rejects.toBeInstanceOf(ApiError);
    expect((await request("/galaxy", () => ({ nodes: [] }), undefined, mk(404), { notFoundIsMock: true })).source).toBe("mock");
    const ok = (async () => new Response(JSON.stringify({ status: "ok" }), { status: 200 })) as unknown as typeof fetch;
    expect(await request("/health", () => ({ status: "m" }), undefined, ok)).toEqual({ data: { status: "ok" }, source: "live" });
  });
});

describe("normalizeGalaxy", () => {
  it("passes a {nodes, clusters, links} graph through", () => {
    expect(normalizeGalaxy(GRAPH)).toEqual(GRAPH);
  });

  it("turns the #8 paper list into nodes and clusters with empty links", () => {
    const graph = normalizeGalaxy(FLAT);
    expect(graph.links).toEqual([]);
    expect(graph.nodes.map((n) => n.topic_id)).toEqual(["W1", "W2", "W3"]);
    expect(graph.nodes.map((n) => n.topic_name)).toEqual(["W1", "W2", "W3"]);
    expect(graph.nodes[0]).toMatchObject({ x: 0.2, y: -1, z: 4, cluster_id: "0", support: 1 });
    expect(graph.clusters).toEqual([
      { id: "0", name: "protein folding" },
      { id: "-1", name: "unclustered" },
    ]);
  });

  it("returns an empty graph for an unexpected body and does not throw", () => {
    for (const raw of [null, undefined, "nope", 3, {}, { nodes: "nope" }, { points: FLAT }]) {
      expect(normalizeGalaxy(raw)).toEqual({ nodes: [], clusters: [], links: [] });
    }
  });

  it("normalizes both live payloads inside api.galaxy", async () => {
    vi.resetModules();
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://api.test");
    vi.stubEnv("NEXT_PUBLIC_API_MOCK", "");
    const { api } = await import("@/lib/api/client");
    const respond = (body: unknown) => {
      vi.stubGlobal("fetch", (async () => new Response(JSON.stringify(body), { status: 200 })) as unknown as typeof fetch);
    };
    respond(GRAPH);
    const first = await api.galaxy();
    expect(first.source).toBe("live");
    expect(first.data).toEqual(GRAPH);
    respond(FLAT);
    const second = await api.galaxy();
    expect(second.source).toBe("live");
    expect(second.data.links).toEqual([]);
    expect(second.data.nodes.map((n) => n.topic_id)).toEqual(["W1", "W2", "W3"]);
    expect(second.data.clusters[0]).toEqual({ id: "0", name: "protein folding" });
    respond({ unexpected: true });
    expect((await api.galaxy()).data).toEqual({ nodes: [], clusters: [], links: [] });
    vi.unstubAllGlobals();
  });
});
