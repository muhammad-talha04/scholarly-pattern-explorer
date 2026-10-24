/** Growth stays hidden: only 72% of 2026 papers carry author countries vs 97% of 2025 (OpenAlex lag), so year-to-date growth is biased down. Set NEXT_PUBLIC_SHOW_GROWTH=1 (or "true") to show it. */
export const SHOW_GROWTH = ["1", "true"].includes((process.env.NEXT_PUBLIC_SHOW_GROWTH ?? "").toLowerCase());

/** Share-of-papers column (share % now and change in percentage points vs the same dates last year). Off unless NEXT_PUBLIC_SHOW_SHARE=1 or "true". */
export const SHOW_SHARE = ["1", "true"].includes((process.env.NEXT_PUBLIC_SHOW_SHARE ?? "").toLowerCase());
