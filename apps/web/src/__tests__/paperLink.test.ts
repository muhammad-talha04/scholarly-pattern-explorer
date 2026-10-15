import { isPlaceholderDoi, readerLink } from "@/lib/paperLink";

it("never links a 10.1234 DOI", () => {
  expect(isPlaceholderDoi("https://doi.org/10.1234/spe.0")).toBe(true);
  const mock = readerLink(
    { title: "Privacy in federated learning", original_url: "https://doi.org/10.1234/spe.0", openalex_url: "https://openalex.org/W4100000000" },
    "mock",
  );
  expect(mock).toEqual({
    href: "https://openalex.org/works?search=Privacy%20in%20federated%20learning",
    label: "Find on OpenAlex",
  });
  const liveFake = readerLink(
    { title: "Privacy in federated learning", original_url: "https://doi.org/10.1234/spe.0", openalex_url: "https://doi.org/10.1234/spe.0" },
    "live",
  );
  expect(liveFake?.href).toBe(mock?.href);
  expect(liveFake?.href).not.toContain("10.1234");
});

it("prefers a real DOI, then a PDF or OpenAlex work", () => {
  expect(readerLink(
    { title: "T", original_url: "https://doi.org/10.1/a", openalex_url: "https://openalex.org/W1" },
    "live",
  )).toEqual({ href: "https://doi.org/10.1/a", label: "Read original paper" });
  expect(readerLink(
    { title: "T", original_url: "https://example.org/w1.pdf", openalex_url: "https://openalex.org/W1" },
    "live",
  )?.href).toBe("https://example.org/w1.pdf");
  expect(readerLink(
    { title: "T", original_url: null, openalex_url: "https://openalex.org/W2" },
    "live",
  )).toEqual({ href: "https://openalex.org/W2", label: "Read original paper" });
  expect(readerLink({ title: "", original_url: null, openalex_url: null }, "mock")).toBeNull();
});
