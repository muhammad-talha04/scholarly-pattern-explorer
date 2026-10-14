import { describe, expect, it, vi, beforeEach } from "vitest";

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
    const ok = (async () => new Response(JSON.stringify({ status: "ok" }), { status: 200 })) as unknown as typeof fetch;
    expect(await request("/health", () => ({ status: "m" }), undefined, ok)).toEqual({ data: { status: "ok" }, source: "live" });
  });
});
