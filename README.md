# Scholarly Pattern Explorer v2

> **Status: Phase 0 (scaffold) on branch `v2-rebuild`.** The original Streamlit app
> (v1) lives untouched in [`legacy/`](legacy/README.md) and keeps running on `main`.

Which combinations of research topics are being born, and which is the field leaving
behind? v2 mines sliding-window frequent topic patterns from OpenAlex, updates them
**incrementally** on a free twice-monthly schedule, and serves them through a 3D web app
with semantic search, paper summaries and chat about a paper.

## Architecture

```
            GitHub Actions cron (1st & 15th)                 Vercel (free)
 OpenAlex ──► pipeline/  fetch → upsert → embed → mine dirty   web/  Next.js + TS + Tailwind
   API        windows → pattern events → runs row              react-three-fiber (galaxy, globe,
                     │                                          3D co-author graph, timeline)
                     ▼                                                    │
            Postgres + pgvector (Supabase/Neon free) ◄──── api/ FastAPI (HF Spaces / Render free)
            works · topics · authors · countries ·          /search /papers /patterns /countries
            embeddings · patterns · rules · runs            /timeline, summaries + chat via a
                                                            free LLM tier (Groq / Gemini)
```

| Folder | What |
|---|---|
| `pipeline/` | Python package `spe_pipeline`: hand-written FP-Growth (ported from v1, still checked against brute force), resumable OpenAlex fetcher (`spe-fetch`, supports `--from-updated` for incremental pulls), idempotent Postgres loader (`spe-load`), window/params bookkeeping for incremental mining |
| `api/` | FastAPI service. `/health` works; `/search`, `/papers/{id}` (+ `/summary`, `/chat`), `/patterns`, `/patterns/lifecycles`, `/countries`, `/timeline` return typed placeholders |
| `web/` | Next.js 14 App Router + TypeScript + Tailwind + react-three-fiber/drei; animated 3D "pattern galaxy" landing scene |
| `db/migrations/` | SQL schema (Postgres 16 + pgvector) |
| `legacy/` | v1 scripts, workflows and README, kept for reference |
| `docs/`, `screenshots/` | v1 public snapshot (still written by `main`'s weekly job) |

### Data model highlights (`db/migrations/0001_init.sql`)
- OpenAlex IDs are keys everywhere; **itemsets are sorted topic IDs** (`T10028|T10320`), not display names.
- `rules` has a real primary key `(scope, window_start, antecedent_key, consequent_id)`.
- `mining_windows` records, per `(scope, window)`, the exact mining params (+ hash), basket digest, `n_tx` and the run that produced it. Patterns/rules cascade from it, so replacing one window is a single delete + insert.
- `runs` logs every pipeline execution (added/updated works, windows mined, patterns born/died, next fetch watermark) and feeds the progress timeline together with `pattern_events`.
- `works.tsv` (full text) + `work_embeddings VECTOR(384)` with HNSW index for hybrid search; `paper_summaries` caches LLM output.
- `scope` = `''` for the whole corpus or an ISO country code for per-country mining.

### Incremental mining (Phase 1)
Windows are fixed year ranges, so an update only affects windows containing the
publication years of new or changed papers (`spe_pipeline.windows.dirty_windows`).
Those windows are re-mined exactly with FP-Growth and swapped in; all other windows'
results are kept. A window whose `params_hash` differs from the current config, or
whose basket digest changed, is also re-mined. The result is identical to a full
re-mine, and a test will enforce that.

## Local development

```bash
cp .env.example .env
docker compose up -d db                      # pgvector Postgres; applies db/migrations on first start

python -m venv .venv && source .venv/bin/activate
pip install -e "pipeline[dev]" -e "api[dev]"
pytest pipeline && (cd api && pytest)        # DB integration test runs when DATABASE_URL is set
ruff check pipeline api

spe-fetch --subfield-id 1702 --min-cited 20 --max-records 2000 --out data/works.jsonl
DATABASE_URL=postgresql://spe:spe@localhost:5432/spe spe-load data/works.jsonl

uvicorn app.main:app --reload --app-dir api  # http://localhost:8000/docs
cd web && npm install && npm run dev         # http://localhost:3000
```

CI (`.github/workflows/ci.yml`) runs ruff, pytest (including the migration + loader
against a pgvector service container), and the web lint/typecheck/build.

## Phased plan

| Phase | Scope |
|---|---|
| **P0 scaffold** ✅ | Monorepo, FP-Growth port + tests, fetcher, loader, schema, compose, CI, landing scene |
| **P1 pipeline** | Incremental miner (dirty windows, global + per country) with an "incremental equals full re-mine" test, pattern events, `runs` logging, v1 DuckDB → Postgres migration, twice-monthly cron (`0 3 1,15 * *`) with concurrency guard |
| **P2 core app** | Real API endpoints; views for topics/co-occurrence, itemsets & rules, lifecycles, emerging/declining; paper pages linking DOI / OpenAlex / OA PDF; Country tab with 3D globe (output bars + collaboration arcs) |
| **P3 AI** | bge-small/MiniLM embeddings in the pipeline, hybrid pgvector + full-text search (RRF), cached paper summaries, per-paper RAG chat (free LLM tier), rate limiting |
| **P4 visuals & timeline** | Pattern galaxy driven by real data, 3D co-author graph, window scrubber, runs history page, perf (instancing, static JSON snapshots) |
| **P5 extras** | Port v1 link prediction as an offline job, trend significance, age-normalised citation filter |

All components target free tiers: GitHub Actions, Vercel Hobby, Supabase/Neon,
Hugging Face Spaces, Groq/Gemini free API.
