import { API_URL, prefersFixtures } from "./client";

/**
 * Server-side prefetch so the first HTML has real rows for crawlers and slow connections.
 * Returns undefined (the client fetches as before) when the API is unset, mocked, slow (Render cold start) or failing.
 */
export async function prefetch<T>(path: string, timeoutMs = 4000): Promise<T | undefined> {
  if (prefersFixtures()) return undefined;
  try {
    const res = await fetch(`${API_URL}/api/v1${path}`, { next: { revalidate: 3600 }, signal: AbortSignal.timeout(timeoutMs) });
    if (!res.ok) return undefined;
    return (await res.json()) as T;
  } catch {
    return undefined;
  }
}
