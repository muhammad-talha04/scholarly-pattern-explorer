import { HOVER_RELEASE_PX, HOVER_STICK_PX, HOVER_SWITCH_MARGIN, leaveClearsHover, resolvePaperHover, resolveTouchPin } from "@/features/galaxy/hover";

it("keeps the locked paper while nodes drift under a still pointer", () => {
  const next = resolvePaperHover({
    locked: 2,
    travelPx: 0,
    hits: [{ id: 5, distance: 4 }, { id: 2, distance: 48 }],
    lockedDistance: 48,
  });
  expect(next).toBe(2);
});

it("ignores tremor and scroll-synthesized pointermove below the stick threshold", () => {
  const next = resolvePaperHover({
    locked: 2,
    travelPx: HOVER_STICK_PX - 0.5,
    hits: [{ id: 9, distance: 1 }],
    lockedDistance: 70,
  });
  expect(next).toBe(2);
});

it("switches only after the pointer travels onto a clearly closer paper", () => {
  const next = resolvePaperHover({
    locked: 2,
    travelPx: 18,
    hits: [{ id: 5, distance: 6 }, { id: 2, distance: 6 + HOVER_SWITCH_MARGIN + 8 }],
    lockedDistance: 6 + HOVER_SWITCH_MARGIN + 8,
  });
  expect(next).toBe(5);
});

it("does not bounce to a neighbour that is only barely closer", () => {
  const next = resolvePaperHover({
    locked: 2,
    travelPx: 18,
    hits: [{ id: 5, distance: 16 }, { id: 2, distance: 16 + HOVER_SWITCH_MARGIN - 1 }],
    lockedDistance: 16 + HOVER_SWITCH_MARGIN - 1,
  });
  expect(next).toBe(2);
});

it("clears the card once the pointer has left the locked paper", () => {
  const next = resolvePaperHover({
    locked: 2,
    travelPx: 24,
    hits: [],
    lockedDistance: HOVER_RELEASE_PX + 12,
  });
  expect(next).toBeNull();
});

it("acquires the paper under the pointer when nothing is locked", () => {
  expect(resolvePaperHover({ locked: null, travelPx: 10, hits: [{ id: 4, distance: 8 }], lockedDistance: null })).toBe(4);
  expect(resolvePaperHover({ locked: null, travelPx: 10, hits: [], lockedDistance: null })).toBeNull();
});

it("pins a touch tap and ignores the pointerleave that follows the lift", () => {
  expect(resolveTouchPin([{ id: 3, distance: 9 }, { id: 1, distance: 22 }])).toBe(3);
  expect(leaveClearsHover("touch")).toBe(false);
  expect(leaveClearsHover("mouse")).toBe(true);
  expect(leaveClearsHover("pen")).toBe(true);
});

it("clears a touch pin on empty space and switches when another paper is tapped", () => {
  expect(resolveTouchPin([])).toBeNull();
  expect(resolveTouchPin([{ id: 7, distance: 6 }])).toBe(7);
});
