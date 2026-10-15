# Project status (read this first)

Last updated: 2026-10-15 05:10 PKT by tom (ML row) and ami (integration tests row); earlier by michal, olli.

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
| Front end and 3D visuals | harry | `web-frontend`, #5 |
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
- Merge order: #1, #3, #2, then front end.
- Release 1 (approved by Prince): search, summaries, ask-about-a-paper,
  countries, progress timeline, research-gap finder.
- Release 2: citation map, topic/author alerts, growing collections,
  side-by-side comparison, influential citations.

## Where we left off
Nothing is merged into main yet.
- [ ] #1 (olli): ready for review, waiting for Prince to merge
- [ ] #3 (grok): draft; fractional-counting change and STATUS entry not pushed yet, waiting on Prince's OK in 1:1
- [ ] #2 (tom): draft. Merge after #1 and #3, because the branch already contains both (merged, not rebased).
  - Done: `ml/` reads `data/works_v2.jsonl` and falls back to the old JSONL. Every contract route in `core.py` is now wired: search, papers, ask, related, patterns and runs go to `ml/`; `/countries`, `/countries/{code}` and `/countries/collaborations` (each with `counting=fractional|full`) go to `pipeline/country_api.py`. `CountryStats.papers` is now a float. Branch has the latest #1, #3 and michal's gap finder merged in. Tests pass: api 12, ml + pipeline 31, `test_fpgrowth`, `test_linkpred`. Ami's #4 integration tests run against this branch: 23 pass, all 7 countries/float xfails now XPASS (fixed), 2 xfails remain (pipeline side).
  - Next: ami can drop the 7 fixed xfails in #4. Index the real `works_v2.jsonl` into pgvector, and make the ingest workflow run `python -m ml.cli index/update`. Grok's side: fractional collaboration counts (the route already takes `counting`; it serves `collaborations_<counting>` from the snapshot if present, else the existing list) and `topic_top_countries` as `[code, fractional_count]` pairs.
  - Blockers: the real all-MiniLM-L6-v2 model and pgvector are untested. The tests use a lightweight offline embedder and a fake database connection. A live run needs a Supabase `DATABASE_URL`.
- [ ] Front end (harry): not started on the shared base (`v2-rebuild` will not be merged); waiting on "start the front end" in 1:1
- [ ] Ami - integration tests: draft PR #4 "Cross-PR integration tests" (`integration-tests`). Latest `ml-service`, `data-pipeline` (#3) and `platform-skeleton` (#1) are merged in.
  - Done: `tests/integration/`, 42 tests: 41 pass, 1 xfail (strict). All 9 earlier xfails now pass: `/countries` routes are wired, `papers` is a float, collaborations have counting modes, and `topic_top_countries` is pairs. New: per paper, fractional pair weights sum to 1, `per_country` pair weights sum to (n-1)/2, and a single-country paper has no pairs. Incremental pair weights equal a full rebuild. `/countries/collaborations?counting=` returns what the snapshot holds for that counting mode.
  - Still xfail: `schemas.CountingMethod` lacks `per_country` (olli), so `?counting=per_country` returns 422. Also, when it is added, `core.py` `collaborations()` (tom) needs a fix: it looks up `collaborations_per_country`, but the snapshot key is `collaborations_1n`. It then falls back to `country_api.collaborations(limit)`, which passes limit as the counting argument and would serve fractional weights.
  - Next: flip the last xfail once both land. Snapshot collaboration weights are rounded to 2 decimals, so sums in the snapshot are only approximately 1.
- [ ] Gap finder + search query set (michal, senior researcher): built on `ml-service` (#2).
  - Done: `ml/gaps.py`. For each topic, growth is the smoothed, clipped mean year-over-year growth over the last 3 complete years, capped at the median so a one-off spike is damped. Volume is the number of papers in that window. Minimum counts: 20 papers in the window and 5 in the last year. Gap score = growth percentile minus volume percentile. Top countries use fractional counting. `/api/v1/patterns?trend=gap` returns `Pattern` with `items=[topic]` and `support=gap_score`, plus new optional fields `gap_score`, `growth_rate`, `paper_count` and `top_countries` (olli: please review the `schemas.py` addition). `eval/search_queries.jsonl` has 35 queries, and `eval/run_search_eval.py` computes recall@10 and nDCG@10 (see `eval/README.md`). Tests: `ml/tests/test_gaps.py`, `ml/tests/test_search_eval.py`, and the gap route in `apps/api/tests/test_ml_routes.py`.
  - For grok: please add these keys to `data/country_snapshot.json`: `topic_year_counts` as `{topic: {"YYYY": papers}}` and `topic_top_countries` as `{topic: [[code, fractional_count], ...]}` sorted descending. The gap finder uses them when present. Until then it computes both from `data/works_v2.jsonl` (path override: `COUNTRY_SNAPSHOT` env).
  - Next: fill `openalex_ids` in the query set from the real `works_v2.jsonl`, then report MiniLM numbers. Relevance is keyword- and topic-based for now; the repo has no work IDs.
- [ ] Optional: `OPENALEX_MAILTO` repo secret
