# Embedding evaluation (council roadmap item 6), bob, 2026-10-16

Repo `main` at 12b1c56; branch `origin/ami/fastembed-backend` (77e212e) checked out as a worktree in
`/workspace/bob-spe/fastembed-branch` and used as-is (`ml.embeddings.HashEmbedder` / `FastEmbedder`).
Everything here was read-only against remote services (no Supabase writes).

## Corpus
- **The exact live corpus was used: all 14,159 papers.** Title and abstract come from `paper_embeddings.meta`
  in Supabase, read with SELECT only. Text = `Paper.text` ("title. abstract"), the same string the indexer embeds.
  3,288 of the papers have no abstract.
- Sanity check: local hash ranking for "quantum error correction" matches the live API exactly (same ids, same
  scores 0.6547 / 0.6405 / 0.4965), so the local hash numbers are the production numbers.
- **The release asset `works_v2.jsonl` (515 MB) is NOT the live corpus.** It holds **50,000** unique works,
  all published 2025-10 or later (dates run 2025-10 .. 2026-10, plus a few bogus future dates up to 2031).
  It has no type or primary_topic fields in `raw`, so I can't verify the filter. Only **2,999** of the
  14,159 live works are in it; 11,160 are missing, including all 3,102 from 2024.
  The release `galaxy.json` also has 50,000 nodes, so it doesn't match the live 14,159-node galaxy either.
  The 14,159-row JSONL from the handover exists only on the old maintainer box, but Supabase `meta`
  can rebuild it.

## Test set
`queries.csv`: 10 exact-term and 10 plain-language paraphrases, in pairs (E01↔P02 and so on).
They include all six council queries. Protein folding (E04, P10) is the "outside the corpus" probe.
The corpus actually has 2 real protein-structure papers (AlphaFold2 DeepSHAP; quantum binding-site
structure prediction), so a good embedder *should* return them.
`ooc_calibration.csv`: 5 extra clearly off-topic queries, used only to calibrate the score cutoff.
Judgments: binary and strict (the paper must be *about* the intent), made from the title and abstract
against the per-query rule in `queries.csv`. Pooled across the three embedders, so each paper has one
judgment per query. All 600 rows are in `judgments.csv`.

## Relevance results (`summary.json`)
| | hash | bge-small-en-v1.5 (fastembed) | all-MiniLM-L6-v2 (fastembed) |
|---|---|---|---|
| In-corpus queries with top-5 mostly relevant (≥3/5), of 18 | **9** | **18** | **16** |
| same, stricter ≥4/5 | 7 | 17 | 15 |
| exact-term (of 9) / paraphrase (of 9) | 9 / **0** | 9 / **9** | 9 / 7 |
| mean P@10, in-corpus | 0.48 | 0.88 | 0.88 |
| mean P@10 exact / paraphrase | 0.80 / 0.16 | 0.97 / 0.79 | 0.99 / 0.77 |
| Council tumour query P01, top-5 / top-10 relevant | 0/5, 0/10 | 4/5, 8/10 | 2/5, 6/10 |
| eval/ qrels: rank of the 4 judged papers present in corpus | 108, 54, 614, >1000 | 1, 2, 8, 4 | 8, 5, 227, 55 |
| qrels nDCG@10 (3 queries) / Recall@20 | 0.00 / 0.00 | 0.70 / 1.00 | 0.23 / 0.67 |

Council target: ≥7/10 mostly relevant, i.e. ≥13 of the 18 in-corpus queries (70%).
Hash fails (50%; every paraphrase fails). bge passes (100%) and MiniLM passes (89%; it misses
P01 tumours and P09 "like or dislike from online posts").
The eval/ qrels barely overlap the corpus: 7 of 323 pairs, 4 with relevance > 0, across 3 queries.
They are directional only.

## Score cutoff (calibration)
| | relevant hits: min / p10 | irrelevant hits: max | off-topic calibration queries: max of all top-10 | in-corpus top-1: min |
|---|---|---|---|---|
| hash | 0.283 / 0.335 | 0.548 | **0.568** ("history of the roman empire") | 0.306 |
| bge | 0.673 / 0.719 | 0.810 | 0.649 | 0.722 |
| MiniLM | 0.344 / 0.466 | 0.730 | 0.312 | 0.481 |

- **hash: no cutoff is possible.** Off-topic queries score higher than good paraphrase hits, so "off" is correct for hash.
- **MiniLM: 0.38 is confirmed.** It keeps 99% of relevant hits and 0% of off-topic calibration hits.
  "Protein folding" keeps 3 hits (2 relevant) and its paraphrase keeps 0.
- **bge: the cutoff is 0.68**, not 0.38. It keeps 99% of relevant hits and 0% of off-topic hits.
  The margin is narrow (0.649 vs 0.673) because bge squeezes all its scores into 0.55..0.91.
  "Protein folding" still shows 10 hits (2 relevant), so a fixed floor trims less junk with bge than with MiniLM.
- Five calibration queries is a small sample. Keep it per model plus `ML_SEARCH_MIN_SCORE`, and recheck after the re-embed.

## RAM and latency (`api_probe_results.jsonl`)
Method: the real FastAPI app from the branch (`apps/api/app/main.py`) with the local store, and
`/api/v1/search` called through TestClient, so the embedder loads and embeds the query the same way
it does on Render. The pgvector query isn't included; the 14k vectors live in Supabase.
| | peak RSS (app + embedder + 21 searches) | first-ever start (model download, 1 core) | load from cache | warm query embed+search, 1 core, median / max |
|---|---|---|---|---|
| hash | 63 MB | – | 0 s | 2.4 / 3.7 ms |
| bge (Qdrant/bge-small-en-v1.5-onnx-Q, 65 MB) | **294 MB** (319 MB on download) | 7.4 s | 0.4 s | 5.0 / 6.9 ms |
| MiniLM (Qdrant/all-MiniLM-L6-v2-onnx, 87 MB) | **242 MB** (268 MB on download) | 6.9 s | 0.4 s | 3.2 / 4.5 ms |
Worst-case 512-token query, embedder only: bge 264 MB / 53 ms, MiniLM 225 MB / 15 ms.
Both fit in 512 MB with roughly 190 MB (bge) and 245 MB (MiniLM) of headroom. That headroom also has
to cover the live snapshot, galaxy caches and psycopg pool, which I didn't measure because there's no
Render metrics access. Render's fractional CPU will make embedding several times slower, but it stays
far below the 1.6 s `vector` stage seen in live Server-Timing.

## Full re-embed estimate (this box, 8 vCPU, shared, load avg ~9)
Measured over all 14,159 papers in batches of 1000, fed to fastembed 32 texts at a time. Embedding only;
the Supabase upsert time isn't included (no writes allowed).
| | papers/s | 14,159 papers | ~70,000 papers | indexer peak RSS |
|---|---|---|---|---|
| hash | 4,000 | 4 s | 18 s | 0.15 GB |
| bge (512-token window) | 18 | **13 min** | **~64 min** | 1.5 GB |
| MiniLM (256-token window, truncates ~longest abstracts) | 106 | **2.2 min** | **~11 min** | 0.8 GB |
A 4-vCPU GitHub runner would take about twice as long (bge ~2 h for 70k).

## Recommendation
**Use fastembed `BAAI/bge-small-en-v1.5`, with a per-model floor of 0.68.**
It is the only candidate that passes every in-corpus query (18/18, all 9 paraphrases) and the council's
tumour query (4/5). It is clearly best on the qrels, and it fits in 512 MB (294 MB peak).
Costs: re-embedding is 6× slower than MiniLM (~1 h for 70k), the cutoff margin is thin, and it uses
~50 MB more RAM.
MiniLM is the fallback, with the 0.38 floor confirmed. It has better cutoff behaviour and faster indexing,
but it misses 2 of 9 paraphrases, including the tumour query.
Hash should not be used for a "search by meaning" site: 0/9 paraphrases and no usable cutoff.

## Problems in `ami/fastembed-backend`
1. **Indexer memory blow-up.** `FastEmbedder.encode` passes the whole indexer batch (1000) to
   `TextEmbedding.embed()`, which uses fastembed's default internal `batch_size=256`. With bge's 512-token
   window the process reached **8.6 GB RSS** on this box before I killed it. Pass `batch_size=32` (or ≤64)
   to `embed()`.
2. **The floor is wrong for bge.** `min_search_score` returns 0.38 for every non-hash model. bge's off-topic
   hits score 0.55–0.65, so with bge the floor never triggers and "no close matches" never appears.
   Make it per model: hash 0, MiniLM 0.38, bge 0.68.
3. **Unverifiable calibration claim.** The docstring cites a "23-query relevance set (best off-topic 0.34,
   weakest real 0.42)". No such set or script is in the repo. My numbers (0.31 / 0.48) agree on 0.38 for
   MiniLM, but the reference should point at this eval.
4. **The model label can't tell backends apart.** `model_label` gives `BAAI/bge-small-en-v1.5@main` for both
   fastembed and sentence-transformers. fastembed's bge is Qdrant's **quantized** ONNX export
   (`model_optimized.onnx`), so its vectors are not the same as torch bge. The indexer's mixed-model guard
   would let them mix. Include the backend and source in the label, e.g.
   `fastembed:Qdrant/bge-small-en-v1.5-onnx-Q@<rev>`.
5. **Model download on every cold start.** fastembed caches in `/tmp/fastembed_cache`, and Render free has
   an ephemeral disk, so each cold start re-downloads 65–87 MB from Hugging Face (~7 s here, plus a runtime
   dependency on HF). Set `FASTEMBED_CACHE_PATH` inside the build dir and pre-download in `buildCommand`.
6. **Dependency hygiene.** `fastembed>=0.3` is unpinned (0.9.0 installed today), and in `ml/requirements.txt`
   it sits under the `# tests` heading. Pin it (e.g. `fastembed==0.9.0`).
7. **No tests** for `FastEmbedder`, `get_embedder("fastembed")` or `min_search_score`. The existing suites
   still pass on the branch with hash (ml 74 passed / 1 skipped, api 28 passed).
8. **Not yet wired up:** `render.yaml` still says `ML_EMBEDDER=hash`, and `v2-ingest.yml` still has no
   `ML_EMBEDDER`/`ML_EMBED_MODEL` (the workflow must stay disabled until both are pinned).

## Files in this folder
- `queries.csv`: the 20 test queries, with kind, pair and the per-query relevance rule.
- `ooc_calibration.csv`: 5 off-topic queries used only to calibrate the cutoff.
- `judgments.csv`: 600 judged rows (embedder, query, rank, work_id, cosine score, relevant 0/1, title).
- `summary.json`: per-embedder metrics and per-query top-5/top-10 counts and top-1 scores.

Not committed, because they are large or regenerable: the 14,159-paper corpus export, the vectors (`.npy`),
and the scripts' raw outputs. They are on the shared box under `/workspace/bob-spe/` (`data/`, `eval-embedder/`).
The corpus can be rebuilt with a read-only `SELECT work_id, meta FROM paper_embeddings`.

## Status of the branch issues
All 8 problems listed above are addressed in `bob/fastembed-bge`, which supersedes #30
(see the PR and `docs/STATUS.md`, 2026-10-16 bob).
