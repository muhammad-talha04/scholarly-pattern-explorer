/** Pointer travel below this is tremor or a scroll-synthesized pointermove. */
export const HOVER_STICK_PX = 4;
/** Another paper must be this many pixels closer before the card switches. */
export const HOVER_SWITCH_MARGIN = 12;
/** Drop the card once the locked paper's centre is farther than this from the pointer. */
export const HOVER_RELEASE_PX = 36;

export interface PaperHit {
  /** Stable InstancedMesh index. The same paper keeps this id while it drifts. */
  id: number;
  /** Screen pixels from the pointer to that instance's centre. */
  distance: number;
}

/**
 * Keep the card on the paper it acquired while the pointer has not travelled.
 * Drift and orbit move spheres under a still pointer, and the browser also
 * emits pointermove with zero travel while the page scrolls. Those events must
 * not retarget the card. After the pointer actually moves, stay on the locked
 * instance until the pointer leaves it, and switch only when another paper is
 * clearly closer.
 */
export function resolvePaperHover(args: {
  locked: number | null;
  travelPx: number;
  hits: PaperHit[];
  lockedDistance?: number | null;
}): number | null {
  const { locked, travelPx, hits } = args;
  if (locked != null && travelPx < HOVER_STICK_PX) return locked;
  let nearest: PaperHit | null = null;
  for (const hit of hits) {
    if (!nearest || hit.distance < nearest.distance) nearest = hit;
  }
  if (locked == null) return nearest ? nearest.id : null;
  const lockedHit = hits.find((hit) => hit.id === locked);
  const lockedDistance = lockedHit ? lockedHit.distance : args.lockedDistance ?? null;
  if (lockedDistance == null) return nearest ? nearest.id : null;
  if (nearest && nearest.id !== locked && nearest.distance + HOVER_SWITCH_MARGIN < lockedDistance) return nearest.id;
  if (lockedDistance <= HOVER_RELEASE_PX) return locked;
  return null;
}
