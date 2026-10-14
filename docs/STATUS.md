# Project status (read this first)

Last updated: 2026-10-14 23:25 PKT by olli.

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
| Research quality, search eval, gap finder | michal | |

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
- [ ] Prince to merge #1
- [ ] Grok to push fractional-counting change to #3 (needs Prince's OK in 1:1)
- [ ] Merge #3, then Tom rebases #2 and wires routes in `core.py`
- [ ] Harry's front end on mock data, then live API
- [ ] Michal's search query set and gap finder (`/patterns?trend=gap`)
- [ ] Optional: `OPENALEX_MAILTO` repo secret
