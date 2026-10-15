# Project status (read this first)

Last updated: 2026-10-15 by harry (front end, merging main), ami (integration tests), tom (ML); earlier by michal, olli.

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
- Collaboration weights: default `fractional` gives each pair 1/(n(n-1)/2), so every paper adds 1; `per_country` gives 1/n per pair; `full` gives 1. `CountryStats.papers` is a float.
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
  - Done: `ml/` reads `data/works_v2.jsonl` and falls back to the old JSONL. Every contract route is wired: search, papers, ask, related, patterns and runs go to `ml/`; `/countries`, `/countries/{code}` and `/countries/collaborations` go to `pipeline/country_api.py` and accept all three `counting` values (fractional, per_country, full). `CountryStats.papers` is a float. The latest #1, #3 and michal's gap finder are merged in. Tests pass: api 18, ml + pipeline 32, `test_fpgrowth`, `test_linkpred`. Ami's #4 run against this branch: 23 pass and all 9 strict xfails now XPASS, so all 9 known failures are fixed.
  - Next: ami removes the 9 stale xfail markers in #4. Index the real `works_v2.jsonl` into pgvector, and make the ingest workflow run `python -m ml.cli index/update`.
  - Blockers: the real all-MiniLM-L6-v2 model and pgvector are untested. The tests use a lightweight offline embedder and a fake database connection. A live run needs a Supabase `DATABASE_URL`.
- [x] Data paths anchored to the repo root (lura, `fix/anchor-data-paths`, #7): `ml/paths.py` resolves `ML_DATA_DIR`, `COUNTRY_SNAPSHOT` and the works JSONL from the repo root, used by `ml/service.py`, `ml/store.py`, `ml/papers.py`, `pipeline/country_api.py` and `apps/api/app/ml_bridge.py`. The API now finds its data whatever directory it is started from. Test: `ml/tests/test_paths.py`.
- [ ] Front end (harry - developer): draft PR on `web-frontend` (#5), now merging latest main (#1, #2, #3, #4, #7). `v2-rebuild` is abandoned.
  - Done: `apps/web` (Next.js 14 App Router, TypeScript, Tailwind, react-three-fiber/drei, Framer Motion). Pages: landing 3D topic galaxy with research-gap layer (`/patterns?trend=gap`) and search; search with country/year filters, side panel (summary, ask, related, "Read original paper"); countries 3D globe (bars, collaboration arcs, fractional/full toggle with a visible label); progress timeline with scrubber; patterns (itemsets, derived rules, lifecycles, gaps). 2D fallback for reduced motion, low power or no WebGL. Typed client mirrors `schemas.py`; mock fixtures are used when the API is unset, unreachable or returns 501. Vitest 12 tests; lint, typecheck and build pass; `web` job added to `tests` CI.
  - Waiting on grok / talha (#6): populated `/countries` snapshot and `/topic-country-years`. The empty `/countries` list still falls back to fixtures. `/countries/collaborations` is wired on main.
  - Notes for olli: born/died per run is derived client-side from `/patterns` windows (Run only has `patterns_changed`); association rules are derived client-side from itemsets. Types are hand-mirrored in `src/lib/api/types.ts` until openapi codegen is wired.
- [x] Ami - integration tests: PR #4 merged. `tests/integration/`, 42 tests. `/countries` routes are wired, `papers` is a float, collaborations have counting modes, and `topic_top_countries` is pairs. Per paper, fractional pair weights sum to 1, `per_country` pair weights sum to (n-1)/2, and a single-country paper has no pairs. Incremental pair weights equal a full rebuild. `/countries/collaborations?counting=` returns what the snapshot holds for that counting mode. The `core.py` per_country collaboration bug (fixed in #2, 923010a) no longer has an xfail.
  - Next: snapshot collaboration weights are rounded to 2 decimals, so sums in the snapshot are only approximately 1.
- [ ] Gap finder + search query set (michal, senior researcher): built on `ml-service` (#2).
  - Done: `ml/gaps.py`. For each topic, growth is the smoothed, clipped mean year-over-year growth over the last 3 complete years, capped at the median so a one-off spike is damped. Volume is the number of papers in that window. Minimum counts: 20 papers in the window and 5 in the last year. Gap score = growth percentile minus volume percentile. Top countries use fractional counting. `/api/v1/patterns?trend=gap` returns `Pattern` with `items=[topic]` and `support=gap_score`, plus new optional fields `gap_score`, `growth_rate`, `paper_count` and `top_countries` (olli: please review the `schemas.py` addition). `eval/search_queries.jsonl` has 35 queries, and `eval/run_search_eval.py` computes recall@10 and nDCG@10 (see `eval/README.md`). Tests: `ml/tests/test_gaps.py`, `ml/tests/test_search_eval.py`, and the gap route in `apps/api/tests/test_ml_routes.py`.
  - For grok: please add these keys to `data/country_snapshot.json`: `topic_year_counts` as `{topic: {"YYYY": papers}}` and `topic_top_countries` as `{topic: [[code, fractional_count], ...]}` sorted descending. The gap finder uses them when present. Until then it computes both from `data/works_v2.jsonl` (path override: `COUNTRY_SNAPSHOT` env).
  - Next: fill `openalex_ids` in the query set from the real `works_v2.jsonl`, then report MiniLM numbers. Relevance is keyword- and topic-based for now; the repo has no work IDs.
- [ ] Optional: `OPENALEX_MAILTO` repo secret
