import { pageMeta, OG_IMAGE } from "@/lib/seo";

test("every page's metadata carries the shared Open Graph image", () => {
  const m = pageMeta("/countries", "t", "d");
  expect((m.openGraph as { images: unknown[] }).images).toEqual([OG_IMAGE]);
  expect((m.twitter as { images: string[] }).images).toEqual([OG_IMAGE.url]);
  expect(OG_IMAGE.url.endsWith("/opengraph-image")).toBe(true);
});
