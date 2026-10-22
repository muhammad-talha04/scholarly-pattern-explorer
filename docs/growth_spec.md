# Country growth metric spec (for pipeline/country_stats.py)

1. Window: current = Jan 1 .. cutoff of current year; previous = Jan 1 .. same month/day of previous year.
   cutoff = max publication_date in corpus (not today's date), so ingest lag doesn't bias it.
2. growth_pct = (cur - prev) / prev * 100, using the active counting mode (fractional by default).
3. Show only if cur >= 30 AND prev >= 30 (same counting mode). Otherwise growth_pct = null, reason = "too_few_papers".
4. Hide any comparison whose window touches 2024 (partial at both ends), reason = "partial_year".
5. Output per country: growth_pct, cur_count, prev_count, window_start, window_end, reason. Round to 1 decimal.
6. Sanity check: after the fix, the median growth across shown countries should not be below -50%;
   if it is, the year bucketing is wrong (council kill criterion). Add this as a test.
