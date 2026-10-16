import type { Metadata } from "next";

export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? "https://scholarly-pattern-explorer.vercel.app").replace(/\/$/, "");
export const SITE_NAME = "Scholarly Pattern Explorer";

export const ROUTES = ["/", "/search", "/countries", "/timeline", "/patterns", "/compare", "/collections", "/about"] as const;

export function pageMeta(path: string, title: string, description: string, opts: { noindex?: boolean } = {}): Metadata {
  const url = `${SITE_URL}${path === "/" ? "" : path}`;
  return {
    title,
    description,
    alternates: { canonical: url },
    openGraph: { type: "website", siteName: SITE_NAME, url, title, description, locale: "en_US" },
    twitter: { card: "summary_large_image", title, description },
    ...(opts.noindex ? { robots: { index: false, follow: true } } : {}),
  };
}
