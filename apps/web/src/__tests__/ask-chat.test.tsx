import { act, fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";

const ask = vi.fn(async (_id: string, question: string) => ({
  data: {
    answer: question.startsWith("What")
      ? "**Wheat** yield. See [the abstract](https://example.test)."
      : `About ${question}`,
    sources: ["Attention maps reveal contacts."],
  },
  source: "mock" as const,
}));

vi.mock("@/lib/api/client", () => ({ api: { ask } }));

async function askQuestion(input: HTMLElement, value: string) {
  await act(async () => {
    fireEvent.change(input, { target: { value } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
  });
}

test("a follow-up sends only the last two turns as plain text", async () => {
  const setItem = vi.spyOn(Storage.prototype, "setItem");
  const { AskChat } = await import("@/features/search/AskChat");
  const { rerender } = render(<AskChat paperId="W1" />);
  const input = screen.getByLabelText("Ask about this paper");

  await askQuestion(input, "What do attention maps reveal?");
  expect(ask).toHaveBeenCalledWith("W1", "What do attention maps reveal?", []);
  expect(await screen.findByText(/Wheat/)).toBeInTheDocument();

  await askQuestion(input, "explain that more simply");
  expect(ask).toHaveBeenLastCalledWith("W1", "explain that more simply", [
    { role: "user", content: "What do attention maps reveal?" },
    { role: "assistant", content: "Wheat yield. See the abstract." },
  ]);
  expect(await screen.findByText("About explain that more simply")).toBeInTheDocument();

  await askQuestion(input, "what about the second one?");
  expect(ask).toHaveBeenLastCalledWith("W1", "what about the second one?", [
    { role: "user", content: "explain that more simply" },
    { role: "assistant", content: "About explain that more simply" },
  ]);

  rerender(<AskChat paperId="W2" />);
  await askQuestion(screen.getByLabelText("Ask about this paper"), "And the method?");
  expect(ask).toHaveBeenLastCalledWith("W2", "And the method?", []);
  expect(setItem).not.toHaveBeenCalled();
});
