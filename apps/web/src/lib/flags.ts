/** Growth trends stay hidden until the paper sample is rebalanced. Set NEXT_PUBLIC_SHOW_GROWTH=1 (or "true") to turn them back on. */
export const SHOW_GROWTH = ["1", "true"].includes((process.env.NEXT_PUBLIC_SHOW_GROWTH ?? "").toLowerCase());

/** Share-of-papers column (share % now and change in percentage points vs the same dates last year). Off unless NEXT_PUBLIC_SHOW_SHARE=1 or "true". */
export const SHOW_SHARE = ["1", "true"].includes((process.env.NEXT_PUBLIC_SHOW_SHARE ?? "").toLowerCase());
