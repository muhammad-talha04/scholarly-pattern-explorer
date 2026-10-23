import { cardBoxBeside, cardOffsetFromCenter, createHoverLock, pickClosestPaper, reduceHover, type HoverInput, type HoverLock } from "@/features/galaxy/hoverLock";

const card = cardBoxBeside({ x: 100, y: 100 }, { width: 800, height: 600 }, 208, 96);

function sample(over: Partial<HoverInput> & Pick<HoverInput, "hitId">): HoverInput {
  return {
    moving: true,
    hitAt: over.hitId ? { x: 400, y: 300 } : null,
    pointer: over.hitId ? { x: 400, y: 300 } : { x: 10, y: 10 },
    movement: { x: 12, y: 0 },
    overCard: false,
    nextCard: card,
    ...over,
  };
}

function move(state: HoverLock, hitId: string | null, extra: Partial<HoverInput> = {}) {
  return reduceHover(state, sample({ hitId, ...extra }));
}

it("opens the moment the pointer touches a paper and ignores empty space", () => {
  const opened = move(createHoverLock(), "Paper A", { hitAt: { x: 100, y: 100 }, pointer: { x: 100, y: 100 } });
  expect(opened.id).toBe("Paper A");
  expect(opened.anchor).toEqual({ x: 100, y: 100 });

  const missed = move(createHoverLock(), null);
  expect(missed.id).toBeNull();
});

it("replaces the card as soon as the pointer touches a different paper", () => {
  const opened = move(createHoverLock(), "Paper A", { hitAt: { x: 100, y: 100 }, pointer: { x: 100, y: 100 } });
  const next = move(opened, "Paper B", { hitAt: { x: 400, y: 280 }, pointer: { x: 400, y: 280 }, movement: { x: 20, y: 4 } });
  expect(next.id).toBe("Paper B");
  expect(next.anchor).toEqual({ x: 400, y: 280 });
});

it("keeps the card while the pointer crosses empty space", () => {
  const opened = move(createHoverLock(), "Paper A", { hitAt: { x: 100, y: 100 }, pointer: { x: 100, y: 100 } });
  const gap = move(opened, null, { pointer: { x: 160, y: 140 }, movement: { x: 8, y: 2 } });
  expect(gap.id).toBe("Paper A");
});

it("keeps the card while the pointer is still, even if another paper drifts underneath", () => {
  const opened = move(createHoverLock(), "Paper A", { hitAt: { x: 100, y: 100 }, pointer: { x: 100, y: 100 } });
  const still = reduceHover(opened, sample({
    moving: false,
    hitId: "Paper B",
    hitAt: { x: 100, y: 100 },
    pointer: { x: 100, y: 100 },
    movement: { x: 0, y: 0 },
  }));
  expect(still.id).toBe("Paper A");
});

it("locks the paper while the pointer is over the card", () => {
  const opened = move(createHoverLock(), "Paper A", { hitAt: { x: 100, y: 100 }, pointer: { x: 100, y: 100 } });
  const over = move(opened, "Paper B", { overCard: true, pointer: { x: 140, y: 80 }, movement: { x: 6, y: -2 } });
  expect(over.id).toBe("Paper A");
});

it("ignores a paper that sits on the path into the card", () => {
  const opened = move(createHoverLock(), "Paper A", { hitAt: { x: 100, y: 100 }, pointer: { x: 100, y: 100 } });
  const along = move(opened, "Paper B", {
    hitAt: { x: 130, y: 90 },
    pointer: { x: 128, y: 92 },
    movement: { x: 10, y: -2 },
  });
  expect(along.id).toBe("Paper A");
});

it("still switches when a paper is off to the side of that path", () => {
  const opened = move(createHoverLock(), "Paper A", { hitAt: { x: 100, y: 100 }, pointer: { x: 100, y: 100 } });
  const aside = move(opened, "Paper C", {
    hitAt: { x: 100, y: 220 },
    pointer: { x: 100, y: 220 },
    movement: { x: 0, y: 14 },
  });
  expect(aside.id).toBe("Paper C");
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

it("places the card beside the node and flips it back onto the canvas", () => {
  const beside = cardBoxBeside({ x: 100, y: 200 }, { width: 800, height: 600 }, 208, 96);
  expect(beside.left).toBe(114);
  const flipped = cardBoxBeside({ x: 760, y: 200 }, { width: 800, height: 600 }, 208, 96);
  expect(flipped.left).toBe(760 - 208 - 14);
  const centered = cardOffsetFromCenter({ x: 100, y: 200 }, beside);
  expect(centered.x).toBe(beside.left - 100 + beside.width / 2);
  expect(centered.y).toBe(beside.top - 200 + beside.height / 2);
});
