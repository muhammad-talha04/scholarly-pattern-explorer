# Platform v2 architecture

The new platform lives next to the existing Streamlit app, which keeps working
until v2 reaches feature parity. Nothing in the repo root is moved or deleted.

```
apps/web     Next.js + React Three Fiber front end (owner: harry)
apps/api     FastAPI gateway; the contracts below (owner: olli)
  ml/        embeddings, search, summaries, topics (owner: tom, branch ml-service)
pipeline/    scheduled OpenAlex ingestion + country analytics (owner: grok)
tests        per package, run in CI on every push (owner: ami)
```

## Free hosting
Web on Vercel free tier, API on Render or Hugging Face Spaces, Postgres +
pgvector on Supabase free tier, pipeline on GitHub Actions cron (1st and 15th).

## Incremental runs
Every pipeline run writes a row to `runs` and only processes works with
`updated_date > last successful run`. New works are merged into existing
patterns and topics; nothing is rebuilt from scratch. The progress timeline is
the `runs` table plus one snapshot per run.

## API contract (v1)
All routes are under `/api/v1`. Types are defined once in
`apps/api/app/schemas.py`; the web app generates its client from `/openapi.json`.

| Route | Purpose |
|---|---|
| `GET /health` | liveness |
| `GET /search?q=&limit=&country=&year_from=` | meaning-based paper search |
| `GET /papers/{id}` | paper detail, summary, link to the original |
| `POST /papers/{id}/ask` | question about one paper, answered from its text |
| `GET /papers/{id}/related` | related-papers graph |
| `GET /patterns?window=` | mined topic patterns for a window |
| `GET /countries` | per-country whole and fractional counts, growth, and per-year breakdown |
| `GET /countries/{code}` | one country's topics, patterns, collaborators |
| `GET /topic-country-years?limit=` | topic × country × year `paper_count` and `fractional_count`. `limit` defaults to 1000 and is clamped to 1–10000 |
| `GET /runs` | progress timeline of every scheduled run |
| `GET /galaxy` | Stored galaxy graph: `nodes`, `clusters`, `links`. Each node is one paper (`id`, `topic_id`, `topic_name`, `x`, `y`, `z`, `cluster_id`, `cluster_label`, `year`, `support`). `(x, y)` is the 2D layout; `(x, y, z)` is the 3D layout. Embeddings and this payload share the store in `STORAGE.md` |

## Adding a feature
1. Add schemas to `schemas.py` and a router in `app/routers/`.
2. Register it in `app/main.py`.
3. Add a page module in `apps/web` that only talks to the API.
4. Add tests. CI must pass before merge.
