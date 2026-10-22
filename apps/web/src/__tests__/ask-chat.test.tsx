import { act, fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";

const ask = vi.fn(async (_id: string, question: string) => ({
  data: { answer: `About ${question}`, sources: ["Attention maps reveal contacts."] },
  source: "mock" as const,
}));

vi.mock("@/lib/api/client", () => ({ api: { ask } }));

test("a follow-up sends the last two turns", async () => {
  const { AskChat } = await import("@/features/search/AskChat");
  render(<AskChat paperId="W1" />);
  const input = screen.getByLabelText("Ask about this paper");
  await act(async () => {
    fireEvent.change(input, { target: { value: "What do attention maps reveal?" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
  });
  expect(ask).toHaveBeenCalledWith("W1", "What do attention maps reveal?", []);
  expect(await screen.findByText("About What do attention maps reveal?")).toBeInTheDocument();

  await act(async () => {
    fireEvent.change(input, { target: { value: "explain that more simply" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
  });
  expect(ask).toHaveBeenLastCalledWith("W1", "explain that more simply", [
    { role: "user", content: "What do attention maps reveal?" },
    { role: "assistant", content: "About What do attention maps reveal?" },
  ]);
});
