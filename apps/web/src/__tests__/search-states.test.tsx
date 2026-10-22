import { render, screen, fireEvent } from "@testing-library/react";
import { vi } from "vitest";
import { NoCloseMatches, SearchError, SearchLoading, withTimeout } from "@/features/search/SearchPage";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }), useSearchParams: () => new URLSearchParams() }));

test("no close matches suggests broader words and links to patterns and timeline", () => {
  const clear = vi.fn();
  render(<NoCloseMatches filtered onClear={clear} />);
  expect(screen.getByRole("heading", { name: "No close matches" })).toBeInTheDocument();
  expect(screen.getByText(/different or broader words/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /patterns/i })).toHaveAttribute("href", "/patterns");
  expect(screen.getByRole("link", { name: /over time/i })).toHaveAttribute("href", "/timeline");
  fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
  expect(clear).toHaveBeenCalled();
});

test("error state is distinct from the empty state", () => {
  const retry = vi.fn();
  render(<SearchError msg="Search timed out." onRetry={retry} />);
  expect(screen.getByRole("alert")).toHaveTextContent(/Search is unavailable right now/);
  expect(screen.queryByText("No close matches")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(retry).toHaveBeenCalled();
});

test("loading state mentions the server waking up", () => {
  render(<SearchLoading />);
  expect(screen.getByTestId("search-loading")).toHaveTextContent(/may take a moment to wake up/);
});

test("withTimeout rejects slow searches", async () => {
  vi.useFakeTimers();
  const p = withTimeout(new Promise(() => {}), 1000);
  vi.advanceTimersByTime(1001);
  await expect(p).rejects.toThrow(/timed out/);
  vi.useRealTimers();
});
