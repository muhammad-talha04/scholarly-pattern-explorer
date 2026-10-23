# Runbook: halfvec + 70k bulk ingest

Order matters. Each step writes to live Supabase once; do not reorder.

1. **Fixes merged** — 3D-only galaxy, #51, #20, the `v2-ingest` fix (pins
   `ML_EMBEDDER`, runs `python -m db.apply` before ingest, no overlapping runs).
2. **Backfill publication dates** (before re-embed) — `python -m ml.cli backfill-dates --dry-run`,
   then without `--dry-run`. Sets `meta.publication_date` from OpenAlex, 50 ids per
   request; metadata only (vectors and `model` untouched). Resumable and idempotent;
   ids OpenAlex no longer has get `null` and are not retried. ~14k rows ≈ 284 requests,
   ~2 min. `month_counts()` (bulk quotas) prefers it over `meta.created`.
3. **Model switch / re-embed** — set `ML_EMBEDDER` to the new model everywhere
   (Render, Actions, local), then `python -m ml.cli index --reembed --max-db-mb 350`
   (details: `docs/EMBEDDER_SWITCH.md`). **Verify dates survived:**
   `select count(*) from paper_embeddings where meta ? 'publication_date';` before and after
   the re-embed must match; if not, stop and rerun `backfill-dates`.
   Search floor: bge default 0.65 (`ML_MIN_SCORE`, read at runtime; pending chris's benchmark).
   Afterwards `VACUUM (FULL, ANALYZE) paper_embeddings;` to drop dead tuples.
4. **Apply migrations 005 + 006 and deploy the API together** — `DATABASE_URL=... python -m db.apply`. 005 converts
   `embedding` to `halfvec(384)` and rebuilds `paper_embeddings_hnsw` with
   `halfvec_cosine_ops`. Rewrites the table (~15k rows: seconds). Deploy the
   API from this branch in the same window: the old code's `embedding <=> %s::vector`
   search fails against a halfvec column, so search is down until the new API is live.
   **Migration and API deploy are one step**: apply, then immediately redeploy Render
   from the merged main; verify `/search` before continuing. 006 adds `sampling_rates`.
   Search sets `SET LOCAL hnsw.ef_search` per query (`ML_HNSW_EF_SEARCH`, default 100).
5. **Load** — with the same `ML_EMBEDDER`:

       python -m ml.cli bulk --target 55841 --start 2015-01 --index --max-db-mb 300

   `--target` counts *new* papers: 55,841 + the 14,159 stored = 70,000 total.
   Quotas are per publication month and subtract what is already stored that month,
   so the totals end up even. Abstracts shorter than `--min-abstract-chars` (200) are
   skipped. Short months are not marked done; re-running tops them up with a new seed.
   `--max-db-mb` now defaults to 300 everywhere.
   Fetch is resumable (`data/bulk_works.jsonl` + `.state.json`); re-run the same
   command after any failure. Refuses up front if stored rows are from another
   model (ModelMismatch). The size guard stops cleanly at 300 MB.
6. **Single galaxy rebuild** — `python -m ml.cli galaxy --refit`, then discoveries.

Check after each step: `select model, count(*) from paper_embeddings group by 1;`
and `select pg_size_pretty(pg_database_size(current_database()));`

## Sampling rates (for gap / emerging scaling)

`sampling_rates(month date pk, openalex_total int, sampled int, filter text, fetched_at)`
is written by `ml.cli bulk` per month (LocalStore: `<ML_DATA_DIR>/vectors/sampling_rates.json`).
`openalex_total` is OpenAlex `meta.count` for that month with `has_abstract:true`;
RLS is on with one policy: `spe_api` may SELECT (created only if that role exists; re-run `db.apply` after creating it). No write policies; the loader writes as the owner.
`sampled` is papers we hold for that month (stored before + fetched). To compare with
OpenAlex totals, scale a month's count by `openalex_total / sampled`. The min-abstract
filter is applied on our side only, so `openalex_total` slightly over-counts eligible works.
Stored-per-month uses `meta.publication_date` (backfill-dates), else `meta.created`.
