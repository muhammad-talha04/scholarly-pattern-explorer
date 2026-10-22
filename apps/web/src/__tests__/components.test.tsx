import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";
import { CountingToggle } from "@/features/countries/CountingToggle";
import { ResultCard } from "@/features/search/ResultCard";
import { SearchBar } from "@/features/search/SearchBar";
it("counting toggle shows which method is displayed", () => {
  const on = vi.fn();
  const { rerender } = render(<CountingToggle value="fractional" onChange={on} />);
  expect(screen.getByTestId("counting-label")).toHaveTextContent(/Fractional counting/);
  fireEvent.click(screen.getByRole("radio", { name: "Full credit" }));
  expect(on).toHaveBeenCalledWith("full");
  fireEvent.click(screen.getByRole("radio", { name: "Split per pair" }));
  expect(on).toHaveBeenCalledWith("per_country");
  rerender(<CountingToggle value="full" onChange={on} />);
  expect(screen.getByTestId("counting-label")).toHaveTextContent(/Full counting/);
  rerender(<CountingToggle value="per_country" onChange={on} />);
  expect(screen.getByTestId("counting-label")).toHaveTextContent(/Per-country counting/);
});
it("result card renders fields and opens", () => {
  const on = vi.fn();
  render(<ResultCard paper={{ id: "W1", title: "T", authors: ["A", "B"], year: 2024, cited_by: 12, one_line_summary: "S", score: 0.9 }} onOpen={on} />);
  expect(screen.getByText("12 citations")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /12 citations/ })); expect(on).toHaveBeenCalledWith("W1");
});
it("search bar submits trimmed query", () => {
  const on = vi.fn(); render(<SearchBar onSubmit={on} />);
  fireEvent.change(screen.getByLabelText("Search papers"), { target: { value: "  gnn  " } });
  fireEvent.submit(screen.getByRole("search")); expect(on).toHaveBeenCalledWith("gnn");
});
