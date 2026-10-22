# Runbook: halfvec + 70k bulk ingest

Order matters. Each step writes to live Supabase once; do not reorder.

1. **Fixes merged** — 3D-only galaxy, #51, #20, the `v2-ingest` fix (pins
   `ML_EMBEDDER`, runs `python -m db.apply` before ingest, no overlapping runs).
2. **Model switch / re-embed** — set `ML_EMBEDDER` to the new model everywhere
   (Render, Actions, local), then `python -m ml.cli index --reembed`.
   Afterwards `VACUUM (FULL, ANALYZE) paper_embeddings;` to drop dead tuples.
3. **Apply migration 005** — `DATABASE_URL=... python -m db.apply`. Converts
   `embedding` to `halfvec(384)` and rebuilds `paper_embeddings_hnsw` with
   `halfvec_cosine_ops`. Rewrites the table (~15k rows: seconds). Deploy the
   API from this branch at the same time: the new code casts to `::halfvec`.
   (Old code's `::vector` params still work against halfvec via implicit casts
   for writes, but deploy together to be safe.)
4. **Load** — with the same `ML_EMBEDDER`:

       python -m ml.cli bulk --target 55841 --start 2015-01 --index --max-db-mb 300

   `--target` counts *new* papers: 55,841 + the 14,159 stored = 70,000 total.
   Fetch is resumable (`data/bulk_works.jsonl` + `.state.json`); re-run the same
   command after any failure. Refuses up front if stored rows are from another
   model (ModelMismatch). The size guard stops cleanly at 300 MB.
5. **Single galaxy rebuild** — `python -m ml.cli galaxy --refit`, then discoveries.

Check after each step: `select model, count(*) from paper_embeddings group by 1;`
and `select pg_size_pretty(pg_database_size(current_database()));`
