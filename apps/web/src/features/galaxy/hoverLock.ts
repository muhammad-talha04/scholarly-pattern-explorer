/** How long a still pointer must sit on a paper before the card may switch. */
export const HOVER_DWELL_MS = 320;

export type HoverLock = {
  /** Paper the card is showing. Null when no card is open. */
  id: string | null;
  /** Timestamp of the latest sample where the pointer was actually moving. */
  lastMoveAt: number;
  /**
   * Paper under the pointer on the latest moving sample.
   * A dwell tick commits it only when the pointer is still on that same paper.
   */
  pendingId: string | null;
};

export type HoverInput = {
  now: number;
  /** True when this sample has nonzero pointer travel. A dwell tick is false. */
  moving: boolean;
  /** Closest paper under the pointer, or null for empty space and non-paper dots. */
  hitId: string | null;
  /** Pointer is over the open card, including its click target. */
  overCard: boolean;
};

export function createHoverLock(now = 0): HoverLock {
  return { id: null, lastMoveAt: now, pendingId: null };
}

/**
 * The card stays on the paper it opened on while the pointer is traveling,
 * including travel toward the card. It switches only after the pointer has
 * rested on a different paper for {@link HOVER_DWELL_MS}. A still pointer
 * whose hit changes because nodes drifted does not switch: the dwell tick
 * must still see the paper captured when the pointer last moved.
 */
export function reduceHover(state: HoverLock, input: HoverInput): HoverLock {
  if (input.overCard) {
    return {
      id: state.id,
      lastMoveAt: input.moving ? input.now : state.lastMoveAt,
      pendingId: null,
    };
  }
  if (input.moving) {
    return {
      id: state.id ?? input.hitId,
      lastMoveAt: input.now,
      pendingId: input.hitId,
    };
  }
  if (input.now - state.lastMoveAt < HOVER_DWELL_MS) return state;
  if (state.pendingId && state.pendingId !== state.id && input.hitId === state.pendingId) {
    return { id: state.pendingId, lastMoveAt: input.now, pendingId: null };
  }
  return { id: state.id, lastMoveAt: state.lastMoveAt, pendingId: null };
}

/** Nearest paper inside `radius` pixels. Non-paper dots never win. */
export function pickClosestPaper(
  points: readonly { id: string; paper: boolean; x: number; y: number }[],
  px: number,
  py: number,
  radius: number,
): string | null {
  let best: string | null = null;
  let bestD = radius * radius;
  for (const point of points) {
    if (!point.paper) continue;
    const dd = (point.x - px) ** 2 + (point.y - py) ** 2;
    if (dd < bestD) {
      bestD = dd;
      best = point.id;
    }
  }
  return best;
}
