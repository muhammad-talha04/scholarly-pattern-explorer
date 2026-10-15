# Project status (read this first)

Last updated: 2026-10-15 by lura (merge of #6, #8, #9 and #10; #11 under review); earlier by harry (UI v3), tom (ML row) and ami (integration tests row).

## What we are building
Scholarly Pattern Explorer v2: a free web app to search research papers by
meaning, read summaries, ask questions about a paper, open the original, see
emerging topic patterns, country analytics and research gaps, refreshed
incrementally twice a month from OpenAlex. Design: `docs/architecture/`.

## Owners
| Area | Owner | Branch / PR |
|---|---|---|
| Architecture, API contract | olli | `platform-skeleton`, #1 |
| ML: search, summaries, ask, incremental patterns | tom | `ml-service`, #2 |
| OpenAlex ingestion, country analytics | grok | #3 |
| Front end and 3D visuals | harry | #11 (supersedes #5) |
| Tests, competitor research | ami | |
| Research quality, search eval, gap finder | michal | on `ml-service`, #2 |

## Shared-computer rule
All bots share one computer. Each works only in its own clone and never
switches branches in someone else's folder:
olli `/workspace/olli`, tom `/workspace/scholarly-ml`, grok `/workspace/grok-spe`,
harry `/workspace/spe-web`, michal `/workspace/michal-spe`, ami `/workspace/spe-it`. `/workspace/spe` is retired.

## Decisions
- Web app, all free tiers (Vercel, Render or HF Spaces, Supabase, GitHub Actions).
- Schedule: 1st and 15th of each month, incremental only.
- Country counts: fractional by default, full counting as a labelled toggle.
- Collaboration weights: default `fractional` gives each pair 1/(n(n-1)/2), so every paper adds 1; `per_country` gives 1/n per pair; `full` gives 1. `CountryStats.papers` is a float.
- Merge order: #1, #3, #2, then front end.
- Release 1 (approved by Prince): search, summaries, ask-about-a-paper,
  countries, progress timeline, research-gap finder.
- Release 2: citation map, topic/author alerts, growing collections,
  side-by-side comparison, influential citations.

## Where we left off
Merged into main, in order: #1 platform skeleton, #3 OpenAlex ingestion, #2 ML service, #4 integration tests, #7 repo-root data paths, #6 country counts and topic-country-year aggregate, #8 embedding benchmark and galaxy, #9 research gaps / similar / emerging, #10 search qrels and feature shortlist. #11 (UI v3 front end, supersedes the #5 draft) is open.

- [x] #1 platform skeleton and API contract (olli).
- [x] #3 incremental OpenAlex ingestion and country analytics (grok).
- [x] #2 ML service: semantic search, summaries, paper chat, incremental patterns (tom). Every contract route is wired; `/countries*` accept `counting=fractional|per_country|full`.
- [x] Ami - integration tests: PR #4 merged. `tests/integration/`, 42 tests. `/countries` routes are wired, `papers` is a float, collaborations have counting modes, and `topic_top_countries` is pairs. Per paper, fractional pair weights sum to 1, `per_country` pair weights sum to (n-1)/2, and a single-country paper has no pairs. Incremental pair weights equal a full rebuild. `/countries/collaborations?counting=` returns what the snapshot holds for that counting mode. The `core.py` per_country collaboration bug (fixed in #2, 923010a) no longer has an xfail.
  - Next: snapshot collaboration weights are rounded to 2 decimals, so sums in the snapshot are only approximately 1.
- [x] #7 Data paths anchored to the repo root (lura): `ml/paths.py` resolves `ML_DATA_DIR`, `COUNTRY_SNAPSHOT`, `TOPIC_COUNTRY_YEAR_DB` and the works JSONL from the repo root. Test: `ml/tests/test_paths.py`.
- [x] #6 country counts and topic-country-year aggregate: `GET /api/v1/countries` and `/countries/{code}` serve whole `paper_count` and fractional `fractional_count` (1/N over distinct countries) with `by_year`. The aggregate (`topic_id`, `topic_name`, `country_code`, `year`, `paper_count`, `fractional_count`) updates inside each `country_stats` run. SQLite `data/topic_country_year.sqlite`, view `topic_country_year_v`, path `ml/paths.py` `topic_country_year_db()` (repo-root anchored, same rule as `COUNTRY_SNAPSHOT`; override `TOPIC_COUNTRY_YEAR_DB`). DDL in `pipeline/schema_v2.sql`. Endpoint: `GET /api/v1/topic-country-years`.
- [x] #8 Embedding benchmark and paper galaxy (`GET /api/v1/galaxy`):
  - Done: the real `all-MiniLM-L6-v2` model indexes, searches and lays out the sample (`ML_RUN_REAL_EMBED=1`, `ml/tests/test_embedder_real.py`). `python -m ml.benchmark` reads a CSV with columns `query_id,query,work_id,relevance` and scores recall@10 and nDCG@10. On `eval/benchmark_queries.csv` (24 papers, 5 queries) MiniLM, `BAAI/bge-small-en-v1.5` and `intfloat/e5-small-v2` all score recall@10 1.0 and nDCG@10 0.9974, so the default stays MiniLM. A switch needs +0.05 on both metrics. `GET /api/v1/galaxy` returns `id, x, y, z, cluster_id, cluster_label, year` (`(x, y)` is the 2D layout). The PCA basis is frozen, so later runs do not move papers already placed. Summaries and chat accept a local OpenAI-compatible server via `ML_LLM_URL` with no API key (Ollama or llama.cpp); see the README. Offline tests: ml 42 pass (1 skipped real-model test), api 19 pass, integration 42 pass.
  - Next: replace the sample CSV with the hand-labelled query set and re-score. Live pgvector is still untested until a `DATABASE_URL` is available. Install `umap-learn` and `hdbscan` if you want that clusterer once a run has at least 25 papers.
- [x] #9 research gaps, similar papers, emerging topics:
  - Done: `/api/v1/patterns?trend=gap` still returns fast-growing small topics, and now also ranks embedding-space gaps (related topics that rarely appear on the same paper, and topics that are thin next to their nearest neighbors). Each gap includes a short explanation and example papers. `GET /api/v1/papers/{id}/similar` returns nearest neighbours from the existing embedding index with cosine scores. `/api/v1/patterns?trend=emerging` ranks topics by smoothed year-over-year growth (`min` of the mean and the median, with a minimum-count threshold) and takes an optional `country`. Counts are read from `topic_country_year` (`topic_id`, `topic_name`, `country_code`, `year`, `paper_count`, `fractional_count`) when that SQLite table or the snapshot list is present, and otherwise computed from `works_v2.jsonl` in the same shape. `python -m ml.cli discover` (also run at the end of `update`) writes a dated snapshot under the repo-root ML data dir. Paths follow `ml/paths.py`.
  - Next: Call `python -m ml.cli discover` from the 1st/15th workflow after the vector index is in the data store, and let the front end add the gap and emerging views.
- [x] #10 Search qrels, pattern stability, feature shortlist: `eval/search_queries.jsonl` is 40 student queries. `eval/search_qrels.jsonl` maps each one to OpenAlex work ids with relevance 0–2 (`query_id`, `query`, `work_id`, `relevance`). `eval/score_search.py` runs `ml/` search and reports nDCG@10, Recall@20, and MRR; the pytest fixture stays offline. `eval/pattern_stability.py` compares incremental topics and patterns with a full rebuild and reports topic drift and splits. Shortlist of free-tool gaps we can build on OpenAlex: `docs/research/FEATURE_SHORTLIST.md`.
- [ ] #11 Front end (harry) — UI v3, 2026-10-15. `v2-rebuild` stays abandoned. The branch is rebased onto current main (merge, conflicts only in CI and this file) and keeps the web CI job next to the 42 integration tests.
  - Done: dark space design system (tokens, Space Grotesk + Fraunces, glass panels). Galaxy bloom, hover tooltips and a smoothed camera. Globe outlines from Natural Earth 110m (`world-atlas`, public domain) in 3D and in the 2D fallback. Counting toggle now includes `per_country` (country totals stay on the fractional snapshot, matching `country_api`; collaboration weights change). Hero copy sits in a top card so it no longer covers node labels. Nav collapses to a menu at 390px and the search button stays on screen. Empty galaxy and empty globe are designed states (`/?preview=empty` shows the galaxy one). Timeline born/died lists the latest window that actually changed, and a topic streamgraph plus a globe year slider read `GET /topic-country-years`. New client-only pieces: side-by-side `/compare`, collections in `localStorage`, a related-paper map in the paper panel, and a first-run tour. Low-power 2D fallback still covers the galaxy and the globe. Vitest 19; lint and typecheck pass. Integration tests 42, API 18, ml+pipeline 35.
  - Note: `GET /galaxy` (#8) and `GET /topic-country-years` (#6) are now on main, so the galaxy and topic-year views can switch from fixtures to live data.
  - Blocker (lura review): `GET /api/v1/galaxy` on main (#8) returns a list of paper points `{id, x, y, z, cluster_id, cluster_label, year}`, but `apps/web/src/lib/api/types.ts` expects a topic graph `{nodes, clusters, links}`. Against the live API the landing page crashes (`galaxy.nodes` is undefined in `features/galaxy/GalaxyHero.tsx`). Agree one shape, or adapt the response in `lib/api/client.ts`.
  - Next: point `NEXT_PUBLIC_API_URL` at the deployed API and drop the galaxy/topic-year fixtures. OpenAPI codegen can replace the hand-mirrored types.
- [x] Gap finder + search query set (michal): landed with #2; extended by #9 and #10.
  - Done: `ml/gaps.py`. For each topic, growth is the smoothed, clipped mean year-over-year growth over the last 3 complete years, capped at the median so a one-off spike is damped. Volume is the number of papers in that window. Minimum counts: 20 papers in the window and 5 in the last year. Gap score = growth percentile minus volume percentile. Top countries use fractional counting. `/api/v1/patterns?trend=gap` returns `Pattern` with `items=[topic]` and `support=gap_score`, plus new optional fields `gap_score`, `growth_rate`, `paper_count` and `top_countries` (olli: please review the `schemas.py` addition). `eval/search_queries.jsonl` has 35 queries, and `eval/run_search_eval.py` computes recall@10 and nDCG@10 (see `eval/README.md`). Tests: `ml/tests/test_gaps.py`, `ml/tests/test_search_eval.py`, and the gap route in `apps/api/tests/test_ml_routes.py`.
  - Done in #6: the topic-country-year aggregate now provides the per-topic yearly and country counts. (Original request: add these keys to `data/country_snapshot.json`: `topic_year_counts` as `{topic: {"YYYY": papers}}` and `topic_top_countries` as `{topic: [[code, fractional_count], ...]}` sorted descending. The gap finder uses them when present. Until then it computes both from `data/works_v2.jsonl` (path override: `COUNTRY_SNAPSHOT` env).)
  - Next: fill `openalex_ids` in the query set from the real `works_v2.jsonl`, then report MiniLM numbers. Relevance is keyword- and topic-based for now; the repo has no work IDs.

## Open items
- [ ] `OPENALEX_API_KEY` repo secret (free). Without it ingestion stops at 200 papers. Optional: `OPENALEX_MAILTO`.
- [ ] Index the real `works_v2.jsonl` (vector index + galaxy) and run `python -m ml.cli discover` from the 1st/15th workflow.
- [ ] Live pgvector / Supabase `DATABASE_URL` untested; tests use the offline hash embedder.
- [ ] Deploy the API and web app (free tiers) and set `NEXT_PUBLIC_API_URL`.
