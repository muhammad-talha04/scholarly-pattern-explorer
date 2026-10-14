# Project status (read this first)

Last updated: 2026-10-15 05:00 PKT by ami (integration tests row); 04:10 PKT by michal (gap finder + search eval row); earlier by tom, olli.

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
| Front end and 3D visuals | harry | `apps/web` (not yet a PR) |
| Tests, competitor research | ami | |
| Research quality, search eval, gap finder | michal | on `ml-service`, #2 |

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
  - Done: `ml/` reads `data/works_v2.jsonl` and falls back to the old JSONL. Contract routes in `core.py` are wired to `ml/`: search (with country and year filters), papers, ask, related, patterns and runs. Incremental FP-Growth produces dated snapshots. Tests pass: ml 17, api 7, pipeline included in that run, plus the old `test_fpgrowth` and `test_linkpred`.
  - Next: index the real `works_v2.jsonl` on the pgvector store, wire the ingest workflow to run `python -m ml.cli index/update`, add the `/patterns?trend=gap` handler (currently 501; michal owns this).
  - Blockers: the real all-MiniLM-L6-v2 model and pgvector are untested. The tests use a lightweight offline embedder and a fake database connection. A live run needs a Supabase `DATABASE_URL`.
- [ ] Front end (harry): not started on the shared base (`v2-rebuild` will not be merged); waiting on "start the front end" in 1:1
- [ ] Ami - integration tests: draft PR "Cross-PR integration tests" on branch `integration-tests` (based on `ml-service`, #2).
  - Done: `tests/integration/` (offline, small fixtures, run in `.github/workflows/test.yml`): 21 tests, 17 pass, 4 xfail. Covered: `pipeline/ingest.py` output -> `works_v2.jsonl` -> `ml/` reader; `country_stats` output validates against `schemas.CountryStats`; fractional shares sum to 1 per paper (in `ml/gaps.py`); `/api/v1` search, paper detail, ask, related, patterns, runs and `patterns?trend=gap` validate against `schemas.py`; incremental equals full rebuild for ingest, country stats, pattern mining and the vector index; `topic_year_counts` shape.
  - Xfail, flip when fixed: country_stats has no fractional mode on this branch (grok); `/countries` is a stub (olli/tom); snapshot has no `topic_year_counts`/`topic_top_countries` (grok); bug: None topic names from ingest end up in `top_topics` and break `CountryStats` (grok).
  - Next: remove the xfails as #3 lands its changes and `/countries` is wired.
- [ ] Gap finder + search query set (michal, senior researcher): built on `ml-service` (#2).
  - Done: `ml/gaps.py`. For each topic, growth is the smoothed, clipped mean year-over-year growth over the last 3 complete years, capped at the median so a one-off spike is damped. Volume is the number of papers in that window. Minimum counts: 20 papers in the window and 5 in the last year. Gap score = growth percentile minus volume percentile. Top countries use fractional counting. `/api/v1/patterns?trend=gap` returns `Pattern` with `items=[topic]` and `support=gap_score`, plus new optional fields `gap_score`, `growth_rate`, `paper_count` and `top_countries` (olli: please review the `schemas.py` addition). `eval/search_queries.jsonl` has 35 queries, and `eval/run_search_eval.py` computes recall@10 and nDCG@10 (see `eval/README.md`). Tests: `ml/tests/test_gaps.py`, `ml/tests/test_search_eval.py`, and the gap route in `apps/api/tests/test_ml_routes.py`.
  - For grok: please add these keys to `data/country_snapshot.json`: `topic_year_counts` as `{topic: {"YYYY": papers}}` and `topic_top_countries` as `{topic: [[code, fractional_count], ...]}` sorted descending. The gap finder uses them when present. Until then it computes both from `data/works_v2.jsonl` (path override: `COUNTRY_SNAPSHOT` env).
  - Next: fill `openalex_ids` in the query set from the real `works_v2.jsonl`, then report MiniLM numbers. Relevance is keyword- and topic-based for now; the repo has no work IDs.
- [ ] Optional: `OPENALEX_MAILTO` repo secret
