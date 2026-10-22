import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, vi } from "vitest";

const ask = vi.fn();

vi.mock("@/lib/api/client", () => ({ api: { ask } }));

beforeEach(() => {
  ask.mockReset();
  ask.mockImplementation(async (_id: string, question: string) => ({
    data: {
      answer: question.startsWith("What")
        ? "**Wheat** yield. See [the abstract](https://example.test)."
        : `About ${question}`,
      sources: ["Attention maps reveal contacts."],
    },
    source: "mock" as const,
  }));
});

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

test("a long answer is cut to 1000 characters before it is sent", async () => {
  ask.mockImplementation(async () => ({
    data: { answer: "A".repeat(1200), sources: [] },
    source: "mock" as const,
  }));
  const { AskChat } = await import("@/features/search/AskChat");
  render(<AskChat paperId="W1" />);
  const input = screen.getByLabelText("Ask about this paper");
  await askQuestion(input, "Summarise the trial");
  await askQuestion(input, "explain that more simply");
  const history = ask.mock.calls.at(-1)?.[2] as { role: string; content: string }[];
  expect(history).toEqual([
    { role: "user", content: "Summarise the trial" },
    { role: "assistant", content: "A".repeat(1000) },
  ]);
});

test("a failed request is left out of the next history", async () => {
  ask.mockImplementation(async (_id: string, question: string) => {
    if (question === "this will fail") throw new Error("network down");
    return {
      data: { answer: `About ${question}`, sources: [] },
      source: "mock" as const,
    };
  });
  const { AskChat } = await import("@/features/search/AskChat");
  render(<AskChat paperId="W1" />);
  const input = screen.getByLabelText("Ask about this paper");
  await askQuestion(input, "What crop is forecast?");
  await askQuestion(input, "this will fail");
  expect(await screen.findByText("Could not answer: network down")).toBeInTheDocument();
  await askQuestion(input, "explain that more simply");
  expect(ask).toHaveBeenLastCalledWith("W1", "explain that more simply", [
    { role: "user", content: "What crop is forecast?" },
    { role: "assistant", content: "About What crop is forecast?" },
  ]);
});
