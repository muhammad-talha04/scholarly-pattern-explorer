import { createHoverLock, HOVER_DWELL_MS, pickClosestPaper, reduceHover, type HoverLock } from "@/features/galaxy/hoverLock";

function move(state: HoverLock, now: number, hitId: string | null, overCard = false) {
  return reduceHover(state, { now, moving: true, hitId, overCard });
}

function dwell(state: HoverLock, now: number, hitId: string | null, overCard = false) {
  return reduceHover(state, { now, moving: false, hitId, overCard });
}

it("opens on the first paper the pointer moves onto and ignores filler dots", () => {
  const opened = move(createHoverLock(), 1_000, "Paper A");
  expect(opened.id).toBe("Paper A");

  const missed = move(createHoverLock(), 1_000, null);
  expect(missed.id).toBeNull();
});

it("does not switch papers while the pointer is traveling toward the card", () => {
  const opened = move(createHoverLock(), 1_000, "Paper A");
  const traveling = move(opened, 1_040, "Paper B");
  expect(traveling.id).toBe("Paper A");
  const acrossEmpty = move(traveling, 1_080, null);
  expect(acrossEmpty.id).toBe("Paper A");
});

it("keeps the card while the pointer is over it, even if a paper is underneath", () => {
  const opened = move(createHoverLock(), 1_000, "Paper A");
  const over = move(opened, 1_200, "Paper B", true);
  expect(over.id).toBe("Paper A");
  const rested = dwell(over, 1_200 + HOVER_DWELL_MS, "Paper B", true);
  expect(rested.id).toBe("Paper A");
});

it("switches only after the pointer rests on another paper", () => {
  const opened = move(createHoverLock(), 1_000, "Paper A");
  const arrived = move(opened, 1_500, "Paper B");
  const early = dwell(arrived, 1_500 + HOVER_DWELL_MS - 1, "Paper B");
  expect(early.id).toBe("Paper A");
  const rested = dwell(arrived, 1_500 + HOVER_DWELL_MS, "Paper B");
  expect(rested.id).toBe("Paper B");
});

it("does not switch when a different paper drifts under a pointer that already stopped", () => {
  const opened = move(createHoverLock(), 1_000, "Paper A");
  const stopped = move(opened, 1_400, null);
  const drifted = dwell(stopped, 1_400 + HOVER_DWELL_MS, "Paper B");
  expect(drifted.id).toBe("Paper A");
});

it("drops a pending switch when the pointer is no longer on that paper", () => {
  const opened = move(createHoverLock(), 1_000, "Paper A");
  const towardB = move(opened, 1_400, "Paper B");
  const left = dwell(towardB, 1_400 + HOVER_DWELL_MS, null);
  expect(left.id).toBe("Paper A");
  expect(left.pendingId).toBeNull();
});

it("picks the nearest paper and never a closer non-paper dot", () => {
  const points = [
    { id: "dot-1", paper: false, x: 0, y: 0 },
    { id: "Paper A", paper: true, x: 8, y: 0 },
    { id: "Paper B", paper: true, x: 40, y: 0 },
  ];
  expect(pickClosestPaper(points, 0, 0, 12)).toBe("Paper A");
  expect(pickClosestPaper(points, 100, 100, 12)).toBeNull();
  expect(pickClosestPaper(points, 40, 0, 12)).toBe("Paper B");
});
