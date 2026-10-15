# Project status (read this first)

Last updated: 2026-10-15 by country analytics follow-up.

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
| Research quality, search eval, gap finder | michal | |

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
- [x] #1 (olli) and #3 (grok) are merged on main.
- [x] Countries API and fractional counting: `GET /api/v1/countries` (and `/countries/{code}`) serve whole `paper_count` and fractional `fractional_count` from the ingest snapshot, with a per-year breakdown. A paper with authors in N distinct countries adds 1/N to each; whole counts stay. The topic × country × year aggregate (`topic_id`, `topic_name`, `country_code`, `year`, `paper_count`, `fractional_count`) updates inside each `country_stats` run — SQLite `data/topic_country_year.sqlite` view `topic_country_year_v`, DDL in `pipeline/schema_v2.sql` — and is served at `GET /api/v1/topic-country-years`.
- [ ] Next: emerging-topics detector and timeline/globe UI on that aggregate. #2 (tom, ML search/summaries/patterns) is not merged; do not depend on it.
- [ ] Front end (harry): not started on the shared base (`v2-rebuild` will not be merged)
- [ ] Cross-PR tests (ami): not started
- [ ] Gap finder + search query set (michal): not started
- [ ] Optional: `OPENALEX_MAILTO` repo secret
