/** Growth trends stay hidden until the paper sample is rebalanced. Set NEXT_PUBLIC_SHOW_GROWTH=1 (or "true") to turn them back on. */
export const SHOW_GROWTH = ["1", "true"].includes((process.env.NEXT_PUBLIC_SHOW_GROWTH ?? "").toLowerCase());
