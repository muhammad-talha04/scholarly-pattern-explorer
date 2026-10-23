/**
 * Half-width of the lane from a paper to its card. Nodes in that lane are
 * skipped while the pointer is heading into the card, so the click is not stolen.
 */
export const CORRIDOR_PX = 36;

export type Vec = { x: number; y: number };

export type CardBox = { left: number; top: number; width: number; height: number };

export type HoverLock = {
  /** Paper the card is showing. Null when no card is open. */
  id: string | null;
  /** Screen position of that paper when the card opened. The card does not follow drift. */
  anchor: Vec | null;
  /** Card rectangle frozen at open time, in the same space as `anchor`. */
  card: CardBox | null;
};

export type HoverInput = {
  /** False for a still pointer, including the zero-movement events fired while nodes drift. */
  moving: boolean;
  /** Closest paper under the pointer. Null for empty space and non-paper dots. */
  hitId: string | null;
  /** Screen position of `hitId`. */
  hitAt: Vec | null;
  pointer: Vec;
  movement: Vec;
  /** Pointer is over the open card, including its button. */
  overCard: boolean;
  /** Where the card would sit if `hitId` became the open paper. */
  nextCard: CardBox | null;
};

export function createHoverLock(): HoverLock {
  return { id: null, anchor: null, card: null };
}

/**
 * A paper under a moving pointer opens or replaces the card immediately.
 * Empty space keeps the current card. A still pointer never retargets, so
 * drift under a resting cursor cannot swap papers. Nodes on the direct path
 * from the open paper to its card are ignored while the pointer heads that way.
 * Leaving the web is the caller's job: this function does not clear the card.
 */
export function reduceHover(state: HoverLock, input: HoverInput): HoverLock {
  if (!input.moving || input.overCard) return state;
  if (!input.hitId || input.hitId === state.id) return state;
  if (state.id && headingIntoCard(state.anchor, state.card, input.pointer, input.movement, input.hitAt)) {
    return state;
  }
  return {
    id: input.hitId,
    anchor: input.hitAt ?? input.pointer,
    card: input.nextCard,
  };
}

/** True when travel is aimed at the open card and this sample is inside that lane. */
export function headingIntoCard(
  anchor: Vec | null,
  card: CardBox | null,
  pointer: Vec,
  movement: Vec,
  hitAt: Vec | null,
): boolean {
  if (!anchor || !card) return false;
  const target = { x: card.left + card.width / 2, y: card.top + card.height / 2 };
  const dx = target.x - anchor.x;
  const dy = target.y - anchor.y;
  if (movement.x * dx + movement.y * dy <= 0 && Math.hypot(dx, dy) >= 1) return false;
  return inCorridor(anchor, target, pointer) || (hitAt != null && inCorridor(anchor, target, hitAt));
}

function inCorridor(anchor: Vec, target: Vec, point: Vec) {
  const dx = target.x - anchor.x;
  const dy = target.y - anchor.y;
  const len2 = dx * dx + dy * dy;
  if (len2 < 1) return Math.hypot(point.x - anchor.x, point.y - anchor.y) <= CORRIDOR_PX;
  const t = ((point.x - anchor.x) * dx + (point.y - anchor.y) * dy) / len2;
  if (t < -0.25 || t > 1.2) return false;
  const px = anchor.x + dx * t;
  const py = anchor.y + dy * t;
  return Math.hypot(point.x - px, point.y - py) <= CORRIDOR_PX;
}

/**
 * CSS translate for a card whose wrapper is centered on the node (the 3D Html).
 * `cardBoxBeside` is a top-left box; centering shifts that box by half its size.
 */
export function cardOffsetFromCenter(node: Vec, box: CardBox): Vec {
  return {
    x: box.left - node.x + box.width / 2,
    y: box.top - node.y + box.height / 2,
  };
}

/** Card rectangle beside a paper, flipped to stay on the canvas. Same box the views draw. */
export function cardBoxBeside(node: Vec, canvas: { width: number; height: number }, cardW: number, cardH: number): CardBox {
  let left = node.x + 14;
  let top = node.y - cardH * 0.35;
  if (left + cardW > canvas.width - 8) left = node.x - cardW - 14;
  if (left < 8) left = 8;
  if (top < 8) top = 8;
  if (top + cardH > canvas.height - 8) top = Math.max(8, canvas.height - cardH - 8);
  return { left: Math.round(left), top: Math.round(top), width: cardW, height: cardH };
}

/** Nearest paper inside `radius` pixels. Non-paper dots never win. */
export function pickClosestPaper(
  points: readonly { id: string; paper: boolean; x: number; y: number }[],
  px: number,
  py: number,
  radius: number,
): string | null {
  return pickClosestPaperAt(points, px, py, radius)?.id ?? null;
}

export function pickClosestPaperAt(
  points: readonly { id: string; paper: boolean; x: number; y: number }[],
  px: number,
  py: number,
  radius: number,
): { id: string; x: number; y: number } | null {
  let best: { id: string; x: number; y: number } | null = null;
  let bestD = radius * radius;
  for (const point of points) {
    if (!point.paper) continue;
    const dd = (point.x - px) ** 2 + (point.y - py) ** 2;
    if (dd < bestD) {
      bestD = dd;
      best = { id: point.id, x: point.x, y: point.y };
    }
  }
  return best;
}
