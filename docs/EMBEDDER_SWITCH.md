# Runbook: switch production search from hash to fastembed bge-small (re-embed 14,159 rows)

Written 2026-10-16 by bob. Evidence for the choice is in `eval/embedder-2026-10-16/REPORT.md`.
Nothing here has been run yet. Every step that writes to Supabase is marked **WRITE**.

## Why the order matters
- `ml.cli index --reembed` runs `DELETE FROM paper_embeddings` (autocommit) **before** its first batch.
  After that the table only ever holds bge rows, so the table itself is never mixed. During the run the
  corpus is just incomplete (search covers whatever has been written so far).
- The one mismatch window is between "Render serves the new embedder" and "the table holds that
  embedder's rows". The two directions behave differently:
  - **bge query vs hash rows:** cosines come out near 0. The bge floor (0.65, `ML_MIN_SCORE`) drops everything, so users
    see "No close matches". This is harmless.
  - **hash query vs bge rows:** the hash floor is 0, so users get confidently wrong results. Avoid this.
- **So flip Render to bge first, then re-embed.** For a rollback, do the reverse (re-embed to hash first,
  then flip Render).

## 0. Merge this PR (production stays hash)
Render redeploys with `ML_EMBEDDER=hash`. Check that the build log contains
`prefetch: BAAI/bge-small-en-v1.5 ready in .../.cache/fastembed`, and that `/api/v1/health` returns 200.

## 1. Prepare (box, read-only)
```bash
cd /workspace/bob-spe/repo && git checkout main && git pull --ff-only
python3 -m venv .venv-switch && . .venv-switch/bin/activate
pip install -r apps/api/requirements.txt        # fastembed 0.9.0, psycopg, pool; no torch
export DATABASE_URL='<Supabase session pooler URI for spe_api; from the private file, never committed>'
export ML_VECTOR_BACKEND=pgvector
```
Baseline (Supabase SQL editor, or `psql "$DATABASE_URL"`). Record the results in STATUS:
```sql
SELECT count(*) AS n, count(*) FILTER (WHERE model IS NULL) AS null_model FROM paper_embeddings;  -- expect 14159 / 14159
SELECT model, count(*) FROM paper_embeddings GROUP BY 1;
SELECT pg_size_pretty(pg_database_size(current_database()));                                   -- ~90 MB on 2026-10-16
SELECT pg_size_pretty(pg_total_relation_size('paper_embeddings'));
```
Export the corpus that is actually live. This is the re-embed input and the backup.
The release `works_v2.jsonl` is a different set of 50,000 works, so don't use it.
```bash
python -m ml.export_corpus --out data/works_live_14159.jsonl
wc -l data/works_live_14159.jsonl                       # must be 14159
psql "$DATABASE_URL" -Atc "SELECT count(*) FROM paper_embeddings WHERE meta ? 'publication_date'" | tee ~/pubdate-count-before.txt
cp data/works_live_14159.jsonl ~/backup-works_live_14159-$(date +%F).jsonl
psql "$DATABASE_URL" -c "\copy (SELECT kind, payload FROM documents) TO '$HOME/backup-documents-$(date +%F).tsv'"
```
**Size check.** The new vectors are the same `vector(384)` as before. DELETE plus re-insert leaves dead
tuples until VACUUM, so the peak is about 2× the table: roughly 90 MB + ~80 MB ≈ 170 MB, well under the
indexer's `--max-db-mb 350` stop. If the baseline is already above about 250 MB, stop and VACUUM first.

Optional rehearsal, about 13 min, local files only, no writes:
```bash
ML_VECTOR_BACKEND=local ML_DATA_DIR=/tmp/rehearsal ML_EMBEDDER=fastembed ML_EMBED_MODEL=BAAI/bge-small-en-v1.5 \
  python -m ml.cli index --jsonl data/works_live_14159.jsonl --batch-size 1000
```

## 2. Switch (announce about 20 min of degraded search first)
a. **Render:** set `ML_EMBEDDER=fastembed` and `ML_EMBED_MODEL=BAAI/bge-small-en-v1.5`. If the service
   is blueprint-synced, make the change in `render.yaml`, where `ML_EMBEDDER` is `value: hash`; otherwise
   use the dashboard. Then **Save, rebuild and deploy**. The prefetch step is now mandatory and fails the
   build if the model can't be fetched. A failed build keeps the old hash instance serving, which is safe.

b. Wait for the deploy to go live, then confirm the new instance is on bge. With the corpus still hash,
   the floor should make a normal query come back empty:
```bash
curl -s -D- "https://scholarly-pattern-explorer.onrender.com/api/v1/search?q=federated%20learning%20privacy&limit=5" | grep -i -E "server-timing|\"total\""
# expect "total":0 and an embed duration of several ms (hash shows embed;dur=0.2)
```
c. **WRITE: re-embed immediately**, about 13 min of embedding plus the upload:
```bash
ML_EMBEDDER=fastembed ML_EMBED_MODEL=BAAI/bge-small-en-v1.5 \
  python -m ml.cli index --jsonl data/works_live_14159.jsonl --reembed --batch-size 1000 --max-db-mb 350
```
   - If it is interrupted, rerun the same command **without** `--reembed`. Resume is the default, it skips
     ids already written, and the model guard passes because every row has the fastembed label.
     Running `--reembed` again would wipe the rows already written.
   - If it stops at the size limit, VACUUM (step 3) and rerun without `--reembed`.

## 3. Verify and clean up the table
**Dates must survive the re-embed.** `export_corpus` + `Paper` now carry `meta.publication_date`
(including an explicit `null` from `backfill-dates`) and every other meta key through `--reembed`
(`ml/tests/test_reembed_meta.py`). If the `meta ? 'publication_date'` count below differs from the count
taken before the re-embed, stop: do not bulk-load or rebuild the galaxy; rerun
`python -m ml.cli backfill-dates` (it only fills missing keys) and re-check.
```sql
SELECT model, count(*) FROM paper_embeddings GROUP BY 1;   -- exactly one row: fastembed:BAAI/bge-small-en-v1.5@fastembed-0.9.0 | 14159
SELECT count(*) FROM paper_embeddings WHERE meta IS NULL;   -- 0
SELECT count(*) FROM paper_embeddings WHERE meta ? 'publication_date';  -- must equal ~/pubdate-count-before.txt
SELECT count(*) FROM paper_embeddings WHERE meta->>'publication_date' IS NOT NULL;  -- dated rows, same as before
VACUUM (ANALYZE) paper_embeddings;
REINDEX INDEX paper_embeddings_hnsw;                        -- optional at 14k rows; rebuilds the HNSW graph without the deleted hash entries
SELECT pg_size_pretty(pg_database_size(current_database()));
```

## 4. Regenerate everything built on the vectors
a. **WRITE: galaxy.** `--refit` is required, because the frozen PCA basis in `galaxy_state` was fit in hash space:
```bash
ML_EMBEDDER=fastembed ML_EMBED_MODEL=BAAI/bge-small-en-v1.5 python -m ml.cli galaxy --refit
```
   This rewrites the `galaxy`, `galaxy_state` and `galaxy_sample` documents. Render caches parsed galaxy
   docs for `GALAXY_CACHE_TTL` (600 s), so wait 10 min or restart the service. Check:
   `curl -s ".../api/v1/galaxy?limit=600" | python -c "import json,sys;d=json.load(sys.stdin);print(len(d['nodes']),len(d['clusters']))"`

b. **Semantic gaps / discoveries.** These come from the vectors. Write the snapshot into the deployed folder,
   then commit it in a PR (that is a repo write, not a Supabase write):
```bash
SPE_DEPLOY_SNAPSHOTS=1 ML_DATA_DIR=deploy/data/ml COUNTRY_SNAPSHOT=deploy/data/country_snapshot.json \
  ML_EMBEDDER=fastembed ML_EMBED_MODEL=BAAI/bge-small-en-v1.5 python -m ml.cli discover
git checkout -b bob/discoveries-bge && git add deploy/data/ml/snapshots/discoveries-*.json && git commit -m "discoveries: semantic gaps from bge vectors"
```
   `ml_bridge` reads the newest `discoveries-*.json`. Emerging topics and pattern state come from topic
   counts, not vectors, so they don't change.
   The release `galaxy.json` asset (50k nodes, a different corpus) isn't used by the API, so leave it alone.

## 5. Check quality on live
Run the council's six queries against the live API. Expect relevant top results for "teaching computers to
spot tumours in medical scans" and "No close matches" for "medieval french poetry". If the floor is too
tight or too loose, set `ML_MIN_SCORE` on Render (read on every search, no code change or rebuild;
`SEARCH_MIN_SCORE` still overrides it if set). The bge default was lowered from 0.68 to **0.65** on
2026-10-22 and is **pending chris's post-re-embed benchmark**; make the benchmark's number the default.

## 6. Before re-enabling `v2 ingest`
In a separate PR (the token has workflow scope), `v2-ingest.yml` must set
`ML_EMBEDDER=fastembed` and `ML_EMBED_MODEL=BAAI/bge-small-en-v1.5`, install `apps/api/requirements.txt`
(or ml's, which now has `fastembed==0.9.0`), and run `python -m db.apply` before `ml.cli index`.
Never pass `--reembed` there. Only then re-enable the workflow.

## Rollback
1. **WRITE:** `ML_EMBEDDER=hash python -m ml.cli index --jsonl data/works_live_14159.jsonl --reembed`
   (about 4 s of embedding plus the upload). While it runs, the bge instance just shows "No close matches".
2. Flip Render back to `ML_EMBEDDER=hash`.
3. `ML_EMBEDDER=hash python -m ml.cli galaxy --refit`, and restore the old discoveries file from git.
