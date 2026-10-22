import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/seo";

const INDEXED = ["/", "/search", "/countries", "/timeline", "/patterns", "/about"];

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  return INDEXED.map((p) => ({ url: `${SITE_URL}${p === "/" ? "" : p}`, lastModified: now, changeFrequency: "weekly", priority: p === "/" ? 1 : 0.7 }));
}
