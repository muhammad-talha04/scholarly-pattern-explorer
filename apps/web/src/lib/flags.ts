/** Growth trends are on now that the sample is even by month (2015 onward). Set NEXT_PUBLIC_SHOW_GROWTH=0 (or "false") to hide them. */
export const SHOW_GROWTH = !["0", "false"].includes((process.env.NEXT_PUBLIC_SHOW_GROWTH ?? "").toLowerCase());

/** Share-of-papers column (share % now and change in percentage points vs the same dates last year). Off unless NEXT_PUBLIC_SHOW_SHARE=1 or "true". */
export const SHOW_SHARE = ["1", "true"].includes((process.env.NEXT_PUBLIC_SHOW_SHARE ?? "").toLowerCase());
