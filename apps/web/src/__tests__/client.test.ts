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
  it("sends search limit and offset, and omits a galaxy limit unless one is set", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://api.test");
    vi.stubEnv("NEXT_PUBLIC_API_MOCK", "");
    vi.stubEnv("NEXT_PUBLIC_GALAXY_LIMIT", "");
    const { api } = await import("@/lib/api/client");
    const urls: string[] = [];
    vi.stubGlobal("fetch", (async (u: string) => {
      urls.push(String(u));
      if (String(u).includes("/search")) {
        return new Response(JSON.stringify({ query: "privacy", results: [], total: 4, limit: 5, offset: 10 }), { status: 200 });
      }
      return new Response(JSON.stringify({ nodes: [], clusters: [], links: [] }), { status: 200 });
    }) as unknown as typeof fetch);
    const found = await api.search({ q: "privacy", limit: 5, offset: 10 });
    expect(urls[0]).toContain("/search?");
    expect(urls[0]).toContain("limit=5");
    expect(urls[0]).toContain("offset=10");
    expect(found.data.total).toBe(4);
    await api.galaxy();
    expect(urls[1]).toBe("http://api.test/api/v1/galaxy");
    vi.unstubAllGlobals();
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

  it("keeps optional color_index and emerging_score when /galaxy sends them", () => {
    const graph = normalizeGalaxy({
      nodes: [{ ...GRAPH.nodes[0], color_index: 2 }],
      clusters: [{ id: "methods", name: "Methods", color_index: 2, emerging_score: 1.4 }],
      links: [],
    });
    expect(graph.nodes[0].color_index).toBe(2);
    expect(graph.clusters[0]).toEqual({ id: "methods", name: "Methods", color_index: 2, emerging_score: 1 });
  });

  it("keeps the paper title, the OpenAlex topic, and work-id links", () => {
    const raw = {
      nodes: [{
        id: "W1",
        title: "Transformers for protein structure",
        topic_id: "protein-folding",
        topic_name: "Protein folding",
        x: 1, y: 2, z: 3, cluster_id: "0", support: 1,
      }],
      clusters: [{ id: "0", name: "protein, folding" }],
      links: [{ source: "W1", target: "W2", weight: 0.5 }],
    };
    expect(normalizeGalaxy(raw)).toEqual(raw);
  });

  it("treats a blank title as the older title-keyed payload", () => {
    const graph = normalizeGalaxy({
      nodes: [{
        id: "W1", title: "  ", topic_id: "proteins",
        topic_name: "Transformers for protein structure prediction",
        x: 0, y: 0, z: 0, cluster_id: "0", support: 1,
      }],
      clusters: [],
      links: [{ source: "Transformers for protein structure prediction", target: "Other", weight: 1 }],
    });
    expect(graph.nodes[0].title).toBeUndefined();
    expect(graph.nodes[0].id).toBe("W1");
    expect(graph.nodes[0].topic_name).toBe("Transformers for protein structure prediction");
    expect(graph.links[0].source).toBe("Transformers for protein structure prediction");
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

describe("chart aggregates", () => {
  beforeEach(() => { vi.resetModules(); vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

  it("asks for precomputed totals and does not count rows when the route is missing", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://api.test");
    vi.stubEnv("NEXT_PUBLIC_API_MOCK", "");
    const { api } = await import("@/lib/api/client");
    const urls: string[] = [];
    vi.stubGlobal("fetch", (async (u: string) => {
      urls.push(String(u));
      const url = String(u);
      if (url.includes("/aggregates/")) return new Response("{}", { status: 404 });
      if (url.includes("/countries?")) {
        return new Response(JSON.stringify([
          { code: "US", name: "United States", papers: 70, growth_pct: 1, top_topics: [], counting: "fractional", paper_count: 70, fractional_count: 70 },
          { code: "CN", name: "China", papers: 20, growth_pct: 1, top_topics: [], counting: "fractional", paper_count: 20, fractional_count: 20 },
          { code: "IN", name: "India", papers: 10, growth_pct: 1, top_topics: [], counting: "fractional", paper_count: 10, fractional_count: 10 },
        ]), { status: 200 });
      }
      return new Response("[]", { status: 200 });
    }) as unknown as typeof fetch);

    const pubs = await api.publications({ grain: "year" });
    expect(pubs.data).toBeNull();
    expect(pubs.source).toBe("live");
    expect(urls.some((u) => u.includes("/topic-country-years"))).toBe(false);
    expect(urls.some((u) => u.includes("/aggregates/publications?grain=year"))).toBe(true);

    const chart = await api.countryChart({ counting: "fractional", top: 2 });
    expect(chart.data?.items.map((c) => c.code)).toEqual(["US", "CN"]);
    expect(chart.data?.items.map((c) => c.share)).toEqual([70, 20]);
    expect(chart.data?.other).toEqual({ share: 10, countries: 1 });
    expect(urls.some((u) => u.includes("/aggregates/countries?"))).toBe(true);
    expect(urls.some((u) => u.includes("/topic-country-years"))).toBe(false);
    expect(urls.filter((u) => u.includes("scale="))).toHaveLength(0);
  });

  it("uses a live aggregate payload as sent, without rebucketing it", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://api.test");
    vi.stubEnv("NEXT_PUBLIC_API_MOCK", "");
    const { api } = await import("@/lib/api/client");
    const body = {
      counting: "fractional", year: null, top: 1,
      items: [{ code: "US", name: "United States", share: 40 }],
      other: { share: 30, countries: 40 },
    };
    vi.stubGlobal("fetch", (async () => new Response(JSON.stringify(body), { status: 200 })) as unknown as typeof fetch);
    const chart = await api.countryChart({ top: 1 });
    expect(chart.source).toBe("live");
    expect(chart.data?.items[0].share).toBe(40);
    expect(chart.data?.other).toEqual({ share: 30, countries: 40 });
  });
});
