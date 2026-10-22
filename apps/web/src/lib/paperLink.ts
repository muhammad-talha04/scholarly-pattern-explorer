/** Where a paper title should open. Mock rows never point at doi.org. */

const PLACEHOLDER_DOI = /10\.1234(?:\/|$)/i;

export function isPlaceholderDoi(value: string | null | undefined): boolean {
  return Boolean(value && PLACEHOLDER_DOI.test(value));
}

/** A real OpenAlex search for this title. Safe for fixture papers that have no DOI. */
export function openAlexSearchUrl(title: string): string {
  return `https://openalex.org/works?search=${encodeURIComponent(title.trim())}`;
}

export interface ReaderLink {
  href: string;
  label: "Read original paper" | "Find on OpenAlex";
}

function usable(url: string | null | undefined): string | null {
  if (!url || isPlaceholderDoi(url)) return null;
  return url;
}

/**
 * Mock papers open an OpenAlex title search.
 * Live papers prefer the API link (a real DOI, else the PDF, landing page, or OpenAlex work).
 */
export function readerLink(
  paper: { title?: string | null; original_url?: string | null; openalex_url?: string | null },
  source: "live" | "mock",
): ReaderLink | null {
  const title = paper.title?.trim() ?? "";
  const search = title ? openAlexSearchUrl(title) : null;
  if (source !== "live") {
    return search ? { href: search, label: "Find on OpenAlex" } : null;
  }
  const href = usable(paper.original_url) ?? usable(paper.openalex_url);
  if (!href) return search ? { href: search, label: "Find on OpenAlex" } : null;
  if (href.includes("openalex.org/works?") && href.includes("search=")) {
    return { href, label: "Find on OpenAlex" };
  }
  return { href, label: "Read original paper" };
}
