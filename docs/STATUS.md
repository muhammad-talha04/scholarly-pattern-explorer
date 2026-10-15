# Project status (read this first)

Last updated: 2026-10-15 by harry (demo-data links, paper-count badge, Render blueprint); earlier the same day by harry (Embedding Lens plexus breath zoom, Champagne & Platinum, galaxy copy), lura (merged #13, #14, #15 and #11; #16 waiting on token `workflow` permission), tom (ML row) and ami (integration tests row).

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
Merged into main, in order: #1 platform skeleton, #3 OpenAlex ingestion, #2 ML service, #4 integration tests, #7 repo-root data paths, #6 country counts and topic-country-year aggregate, #8 embedding benchmark and galaxy, #9 research gaps / similar / emerging, #10 search qrels and feature shortlist, #12 STATUS cleanup, #13 topic-country-years limit cap, #14 OpenAlex key note, #15 galaxy graph + pgvector/file storage, #11 UI v3 front end. #5 closed (superseded by #11). #16 (precomputed gaps/emerging) is open; see Open items.

- [x] #1 platform skeleton and API contract (olli).
- [x] #3 incremental OpenAlex ingestion and country analytics (grok).
- [x] #2 ML service: semantic search, summaries, paper chat, incremental patterns (tom). Every contract route is wired; `/countries*` accept `counting=fractional|per_country|full`.
- [x] Ami - integration tests: PR #4 merged. `tests/integration/`, 42 tests. `/countries` routes are wired, `papers` is a float, collaborations have counting modes, and `topic_top_countries` is pairs. Per paper, fractional pair weights sum to 1, `per_country` pair weights sum to (n-1)/2, and a single-country paper has no pairs. Incremental pair weights equal a full rebuild. `/countries/collaborations?counting=` returns what the snapshot holds for that counting mode. The `core.py` per_country collaboration bug (fixed in #2, 923010a) no longer has an xfail.
  - Next: snapshot collaboration weights are rounded to 2 decimals, so sums in the snapshot are only approximately 1.
- [x] #7 Data paths anchored to the repo root (lura): `ml/paths.py` resolves `ML_DATA_DIR`, `COUNTRY_SNAPSHOT`, `TOPIC_COUNTRY_YEAR_DB` and the works JSONL from the repo root. Test: `ml/tests/test_paths.py`.
- [x] #13 `GET /api/v1/topic-country-years` `limit` defaults to 1000 and is clamped to 1–10000, same as `/search` and `/related` (below 1 becomes 1, above the max is capped). A non-integer `limit` is still 422.
- [x] #6 country counts and topic-country-year aggregate: `GET /api/v1/countries` and `/countries/{code}` serve whole `paper_count` and fractional `fractional_count` (1/N over distinct countries) with `by_year`. The aggregate (`topic_id`, `topic_name`, `country_code`, `year`, `paper_count`, `fractional_count`) updates inside each `country_stats` run. SQLite `data/topic_country_year.sqlite`, view `topic_country_year_v`, path `ml/paths.py` `topic_country_year_db()` (repo-root anchored, same rule as `COUNTRY_SNAPSHOT`; override `TOPIC_COUNTRY_YEAR_DB`). Postgres DDL is `db/migrations/002_topic_country_year.sql`. Endpoint: `GET /api/v1/topic-country-years`.
- [x] #8 Embedding benchmark and paper galaxy (`GET /api/v1/galaxy`):
  - Done: the real `all-MiniLM-L6-v2` model indexes, searches and lays out the sample (`ML_RUN_REAL_EMBED=1`, `ml/tests/test_embedder_real.py`). `python -m ml.benchmark` reads a CSV with columns `query_id,query,work_id,relevance` and scores recall@10 and nDCG@10. On `eval/benchmark_queries.csv` (24 papers, 5 queries) MiniLM, `BAAI/bge-small-en-v1.5` and `intfloat/e5-small-v2` all score recall@10 1.0 and nDCG@10 0.9974, so the default stays MiniLM. A switch needs +0.05 on both metrics. `GET /api/v1/galaxy` returns `id, x, y, z, cluster_id, cluster_label, year` (`(x, y)` is the 2D layout). The PCA basis is frozen, so later runs do not move papers already placed. Summaries and chat accept a local OpenAI-compatible server via `ML_LLM_URL` with no API key (Ollama or llama.cpp); see the README. Offline tests: ml 42 pass (1 skipped real-model test), api 19 pass, integration 42 pass.
  - Next: replace the sample CSV with the hand-labelled query set and re-score. Live pgvector is still untested until a `DATABASE_URL` is available. Install `umap-learn` and `hdbscan` if you want that clusterer once a run has at least 25 papers.
- [x] #9 research gaps, similar papers, emerging topics:
  - Done: `/api/v1/patterns?trend=gap` still returns fast-growing small topics, and now also ranks embedding-space gaps (related topics that rarely appear on the same paper, and topics that are thin next to their nearest neighbors). Each gap includes a short explanation and example papers. `GET /api/v1/papers/{id}/similar` returns nearest neighbours from the existing embedding index with cosine scores. `/api/v1/patterns?trend=emerging` ranks topics by smoothed year-over-year growth (`min` of the mean and the median, with a minimum-count threshold) and takes an optional `country`. Counts are read from `topic_country_year` (`topic_id`, `topic_name`, `country_code`, `year`, `paper_count`, `fractional_count`) when that SQLite table or the snapshot list is present, and otherwise computed from `works_v2.jsonl` in the same shape. `python -m ml.cli discover` (also run at the end of `update`) writes a dated snapshot under the repo-root ML data dir. Paths follow `ml/paths.py`.
  - Next: Call `python -m ml.cli discover` from the 1st/15th workflow after the vector index is in the data store, and let the front end add the gap and emerging views.
- [x] #10 Search qrels, pattern stability, feature shortlist: `eval/search_queries.jsonl` is 40 student queries. `eval/search_qrels.jsonl` maps each one to OpenAlex work ids with relevance 0–2 (`query_id`, `query`, `work_id`, `relevance`). `eval/score_search.py` runs `ml/` search and reports nDCG@10, Recall@20, and MRR; the pytest fixture stays offline. `eval/pattern_stability.py` compares incremental topics and patterns with a full rebuild and reports topic drift and splits. Shortlist of free-tool gaps we can build on OpenAlex: `docs/research/FEATURE_SHORTLIST.md`.
- [x] #14 OpenAlex free API key: paginated or bulk access past the first page requires `OPENALEX_API_KEY` (free; repo secret, already set). `docs/research/FEATURE_SHORTLIST.md` states that, and every listed feature stays on the free tier. `eval/README.md` and `eval/score_search.py --fetch` say the same: the first page of 50 judged ids is anonymous, and a further page sends the key (the pull stops when the key is missing). Ingestion uses that key the same way (one page is 200 papers). `OPENALEX_MAILTO` stays optional. Offline test: `ml/tests/test_score_search.py`.
- [x] #11 Front end (harry) — UI v3 (merged), 2026-10-15. `v2-rebuild` stays abandoned. The branch is rebased onto current main (merge, conflicts only in CI and this file) and keeps the web CI job next to the 42 integration tests.
  - Done: dark space design system (tokens, Space Grotesk + Fraunces, glass panels). Galaxy bloom, hover tooltips and a smoothed camera. Globe outlines from Natural Earth 110m (`world-atlas`, public domain) in 3D and in the 2D fallback. Counting toggle now includes `per_country` (country totals stay on the fractional snapshot, matching `country_api`; collaboration weights change). Hero copy sits in a top card so it no longer covers node labels. Nav collapses to a menu at 390px and the search button stays on screen. Empty galaxy and empty globe are designed states (`/?preview=empty` shows the galaxy one). Timeline born/died lists the latest window that actually changed, and a topic streamgraph plus a globe year slider read `GET /topic-country-years`. New client-only pieces: side-by-side `/compare`, collections in `localStorage`, a related-paper map in the paper panel, and a first-run tour. Low-power 2D fallback still covers the galaxy and the globe. Vitest 25, lint and typecheck pass. Integration tests 42, API 24, ml + pipeline 75 (1 skipped real-model test).
  - Done (lura review): `normalizeGalaxy` in `apps/web/src/lib/api/client.ts` accepts both galaxy bodies. The #8 list `{id, x, y, z, cluster_id, cluster_label, year}` becomes nodes and clusters with empty links (the paper id is the node id; `cluster_id < 0` is labelled unclustered). `{nodes, clusters, links}` is kept. Any other body becomes an empty graph, and `GalaxyHero` only reads `nodes` when it is an array, so a surprise payload shows the empty state instead of throwing. Vitest covers both shapes and a garbage body. Against a live API returning the #8 list, `/` draws those paper points and stays up. The per-country counting sentence is a full-width wrapping line: at 1280 and 1440 it fits on one line inside the content column, and at 390 it wraps to two lines with no horizontal scroll. Live `GET /topic-country-years` (#6) fills the timeline streamgraph (Quark lattices, Tide models) and moves the countries year slider (Pakistan 9.5 in 2025, 4 in 2024).
  - Next: point `NEXT_PUBLIC_API_URL` at the deployed API and drop the galaxy/topic-year fixtures. OpenAPI codegen can replace the hand-mirrored types. Caster's `{nodes, clusters, links}` response needs no further client change.
- [ ] #18 Galaxy copy (harry): the landing hero, tooltips, topic-cluster legend, first-run tour, `apps/web/README.md`, and the mock galaxy say each dot is a paper. Colors and groups are topic clusters. The galaxy groups papers by theme. Fixture nodes use paper titles, not topic names. Vitest 26, lint and typecheck pass.
- [ ] #18 Embedding Lens (harry): landing matches the reference. Ground is deep navy `#0B0F1A`. The hero is left-aligned: a monospace amber eyebrow, a bold sans headline with “meaning” in amber `#F5A54A`, the line “Each dot is a paper. Nearby papers share ideas, linked by meaning.”, an amber Search button, and suggestion chips. The plexus canvas is full-bleed. A navy scrim keeps the left column readable when the band passes behind it. The drawing is a low-poly plexus: about 310 tiny nodes in one diagonal band, copper `#C2410C` at the lower left, amber `#F5A54A` through the middle, pale gold `#FDE7B0` at the upper right. Cores are a little brighter, a few pixels across, with a faint glow and no hubs. The silhouette feathers instead of ending on a hard notch. Each node links only to nearby neighbours, at most six, and line opacity fades with length. A soft radial wash sits behind the dense middle. One points draw and one line-segment buffer. Motion is 1.5× the first plexus: nodes drift, a few twinkle, and the band yaws continuously around its centre with a small tilt. A 14s breath zooms in until the band fills about 80% of a laptop viewport, holds, zooms back to the right-half size, and holds. There is no scroll-wheel zoom. The loop pauses when the tab is hidden. Reduced motion is static, including the zoom. The 2D canvas uses the same zoom and yaw unless motion is reduced. `?plexus=in` and `?plexus=out` freeze those poses for stills. Colors live in `apps/web/src/lib/palette.ts`. Checked 2026-10-15: vitest 32, lint and typecheck pass. The hero lists 66 papers and overflow is 0. At 1440, zoomed out, the band is 547px wide (38% of the viewport), centered at 70% of the width, with its left edge just past the midpoint, copper at the lower left and pale gold at the upper right. Zoomed in, it is 1173px wide (81% of the viewport) and centered, so it passes behind the hero. The headline stays on navy beside the glyphs. Hot cores are 2px (310 of them). At 390 the band stays under the top scrim when zoomed out and fills the screen when zoomed in, and the headline stays readable. A 20s clip covers a full 14s breath.
- [ ] #18 Champagne & Platinum (harry): one theme file, `apps/web/src/lib/theme.ts`, holds the CSS variables and `clusterColors`. The ground is `#121216`. Champagne `#F3E3B5` is the accent on the headline, search button, focus ring, active nav, and a faint search glow. Galaxy clusters, in order, are champagne gold, platinum, antique gold, pewter, and pale gold, mapped by `color_index` or else the cluster id; anything past five is grey. Charts and the globe use Okabe–Ito. Nodes are one instanced mesh at about 87% brightness, crisp, with a small contact shadow and a thin rim, and no bloom. Drift and twinkle run in the shader and pause when the tab is hidden. Reduced motion keeps the galaxy static, including camera moves, and leaves the hover neighbour glow. `emerging_score` on a cluster, when `/galaxy` sends it, warms that cluster. The 2D fallback stays. A moderate vignette sits behind the hero. Checked 2026-10-15: vitest 30, lint and typecheck pass. Sampled node centers sit near 87% of the cluster hexes, and the disc edge falls off in about one pixel.
- [x] Gap finder + search query set (michal): landed with #2; extended by #9 and #10.
  - Done: `ml/gaps.py`. For each topic, growth is the smoothed, clipped mean year-over-year growth over the last 3 complete years, capped at the median so a one-off spike is damped. Volume is the number of papers in that window. Minimum counts: 20 papers in the window and 5 in the last year. Gap score = growth percentile minus volume percentile. Top countries use fractional counting. `/api/v1/patterns?trend=gap` returns `Pattern` with `items=[topic]` and `support=gap_score`, plus new optional fields `gap_score`, `growth_rate`, `paper_count` and `top_countries` (olli: please review the `schemas.py` addition). `eval/search_queries.jsonl` has 35 queries, and `eval/run_search_eval.py` computes recall@10 and nDCG@10 (see `eval/README.md`). Tests: `ml/tests/test_gaps.py`, `ml/tests/test_search_eval.py`, and the gap route in `apps/api/tests/test_ml_routes.py`.
  - Done in #6: the topic-country-year aggregate now provides the per-topic yearly and country counts. (Original request: add these keys to `data/country_snapshot.json`: `topic_year_counts` as `{topic: {"YYYY": papers}}` and `topic_top_countries` as `{topic: [[code, fractional_count], ...]}` sorted descending. The gap finder uses them when present. Until then it computes both from `data/works_v2.jsonl` (path override: `COUNTRY_SNAPSHOT` env).)
  - Next: fill `openalex_ids` in the query set from the real `works_v2.jsonl`, then report MiniLM numbers. Relevance is keyword- and topic-based for now; the repo has no work IDs.

- [x] #15 Galaxy graph and shared storage:
  - Done: `GET /api/v1/galaxy` returns `{nodes, clusters, links}`. A node is one paper: `id`, `topic_id`, `topic_name`, `x`, `y`, `z`, `cluster_id` (string), `cluster_label`, `year`, `support`. A cluster has `id`, `name`, `label`, `centroid` `{x, y, z}`, and `size`. Links are undirected nearest-neighbour edges (`source`, `target`, `weight`), 2 neighbours, at most 200 edges. `topic_name` is the paper title (work id appended when titles collide) so the web client can draw those edges. `python -m ml.cli index`, `galaxy`, and `update` precompute the payload. The route only reads the stored `galaxy` document and does not scan embeddings. Empty storage returns 200 with empty lists.
  - Storage: one store for embeddings and JSON documents. `DATABASE_URL` selects Postgres + pgvector. `ML_VECTOR_BACKEND=pgvector` forces that backend. `ML_VECTOR_BACKEND=local` forces files under `ML_DATA_DIR` (default `data/ml`) even when `DATABASE_URL` is set. Unset backend follows `DATABASE_URL`. Tables: `paper_embeddings` (`work_id`, `embedding vector(384)`, `meta`, `model`) and `documents` (`kind`, `payload`, `updated_at`). Kinds: `galaxy`, `galaxy_state`, `patterns`, `countries`, `topics`, `topic_country_year`. `store.put_document` / `get_document` are the shared API for topic counts, country counts, and pattern snapshots. Files: `{ML_DATA_DIR}/vectors/documents/{kind}.json`. Details: `docs/architecture/STORAGE.md`. The 1st/15th workflow runs `python -m ml.cli index` and `update` after ingest and uploads `galaxy.json` when the file backend wrote it.
  - Postgres DDL is numbered under `db/migrations/` and applied in order with `DATABASE_URL=... python -m db.apply` (also on `PgVectorStore` connect). `001_vector_storage.sql` is the pgvector extension, `paper_embeddings`, and `documents`. `002_topic_country_year.sql` is `topic_id`, `topic_name`, `country_code`, `year`, `paper_count`, `fractional_count`. `003_discovery_snapshots.sql` is `id`, `run_date`, `kind` (`gap`, `emerging`, and later kinds), optional `country_code`, `results` jsonb, `created_at`, with indexes on `run_date`, `(kind, country_code, run_date)`, and `created_at`. `004_runs_summaries_snapshots.sql` holds `runs`, `paper_summaries`, and `snapshots`. Every table has row level security and no policies, so anon has no access; the API uses `DATABASE_URL`. `pipeline/schema_v2.sql` points at these files. The DuckDB corpus stays in `schema.sql`.
  - Offline tests use the hash embedder and the file backend: ml 73 pass (1 skipped real-model test), api 26 pass, integration 42 pass, pipeline 12 pass.

## Deploy

The web app on Vercel is live. With `NEXT_PUBLIC_API_URL` unset it serves the built-in sample (66 papers). `render.yaml` at the repo root is a Render free-tier blueprint for `apps/api` (the API imports `ml/` and `pipeline/` from the repo root, so the service root is the repository). Build: `pip install -r apps/api/requirements.txt`. Start: `uvicorn app.main:app --app-dir apps/api --host 0.0.0.0 --port $PORT`. Health check: `GET /api/v1/health`. No secret values are in the repo. Free-tier disk is ephemeral, so a file index disappears on restart; a persistent index needs `DATABASE_URL`.

### Live data (2026-10-15)

- API on Render: https://scholarly-pattern-explorer.onrender.com (free tier, `ML_EMBEDDER=hash`). Vercel `NEXT_PUBLIC_API_URL` points at it.
- Supabase project `scholarly-pattern-explorer` (ref `obhzpotvdexzkaeheiun`, region `ap-south-1`, free plan). Migrations 001 to 004 applied; tables are owned by a dedicated login role `spe_api`, so row level security stays on with no policies and the API still reads and writes as the owner. `vector` lives in the `extensions` schema; the role's `search_path` is `public, extensions`.
- Loaded 3000 real OpenAlex works (`primary_topic.subfield.id:subfields/1702`, articles since 2025-10-15) with `python -m pipeline.ingest --max-records 3000`, embedded with `ML_EMBEDDER=hash` (must match the API), plus the `galaxy` and `galaxy_state` documents from `python -m ml.cli index`.
- `apps/api/requirements.txt` now includes `psycopg[binary]`; without it a `DATABASE_URL` makes the API fail on the first store call.
- Render needs `DATABASE_URL` = the Supabase Session pooler string (port 5432, IPv4) for user `spe_api.obhzpotvdexzkaeheiun`. The value is never committed.
- 2026-10-15 expansion: re-ran `python -m pipeline.ingest --first-lookback-days 730 --max-records 12000` (same AI subfield filter, articles since 2024-10-15), merged with the first batch for 14159 unique works, re-indexed with `ML_EMBEDDER=hash`, and upserted every row into `paper_embeddings` (no duplicates; keyed on `work_id`). `galaxy` (14159 nodes) and `galaxy_state` were rebuilt over the full set. Supabase database size went from 28 MB to 91 MB (free tier limit 500 MB).
- Caps: `GALAXY_NODE_LIMIT` is unset by default, so `/galaxy` returns every stored node; set it on Render only if the 14k-node payload (about 4.7 MB) is too heavy for the client. `SEARCH_MAX_LIMIT` defaults to 100 hits per search and does not limit the corpus size.
- 2026-10-15 live snapshots: `deploy/data/` holds snapshots built from the 14159 works with the repo's own pipeline: `country_snapshot.json` (`python -m pipeline.country_stats --new works_v2.jsonl`: 135 countries, 1177 topics, 18115 topic-country-year rows) and `ml/` (`python -m ml.cli update`: pattern state with run 1, 14159 papers, 66 patterns changed, windows 2022 to 2026, plus `discoveries-2026-10-15.json` with 20 emerging topics and 10 semantic gaps). `ml/paths.py` falls back to these files when `COUNTRY_SNAPSHOT` / `ML_DATA_DIR` are unset and `data/` is missing, only when running on Render (Render sets `RENDER=true`) or with `SPE_DEPLOY_SNAPSHOTS=1`, so `/countries`, `/countries/collaborations`, `/topic-country-years`, `/patterns` and `/runs` have data with no Render env change. `SPE_DEPLOY_SNAPSHOTS=0` turns the fallback off; local runs and CI keep the plain `data/` defaults. Refresh by regenerating these files and committing them.
- 2026-10-15 `/patterns?trend=gap` crashed the 512 MB Render instance (HTTP 502) because semantic gaps were computed live over all 14159 vectors. `ml_bridge.get_semantic_gaps` now reads `semantic_gaps` from the newest `{ML_DATA_DIR}/snapshots/discoveries-*.json` first and computes live only when no snapshot exists.
- Pattern and discovery snapshots are still files under `ML_DATA_DIR`, so on the free tier they are rebuilt or missing after a restart.

### API env vars (Render)

Set these in the Render dashboard. `render.yaml` lists them as `sync: false`.

| Variable | Required to boot? | What it does |
|---|---|---|
| `DATABASE_URL` | No | Postgres connection string (pgvector). Unset uses files under `ML_DATA_DIR`. Required for an index that survives a free-tier restart. |
| `ML_VECTOR_BACKEND` | No | `local` forces files even when `DATABASE_URL` is set. `pgvector` forces Postgres and then `DATABASE_URL` is required. Unset follows `DATABASE_URL`. |
| `ML_EMBEDDER` | No | `hash` boots without a model download. Unset loads `sentence-transformers` on the first encode. That package is not in `apps/api/requirements.txt`, so set `hash` on the free tier unless you install it. |
| `ML_EMBED_MODEL` | No | Sentence-transformer id. Default `sentence-transformers/all-MiniLM-L6-v2`. |
| `ML_DATA_DIR` | No | File-backend directory. Default `data/ml`. |
| `ML_WORKS_PATH` | No | Corpus JSONL. Default `data/works_v2.jsonl` when that file exists. |
| `OPENALEX_API_KEY` | No | Ingest and any OpenAlex fetch past the first page. The API process starts without it. |
| `OPENALEX_MAILTO` | No | Polite-pool contact email for OpenAlex. |
| `ML_LLM_URL` | No | OpenAI-compatible URL for summaries and ask. Unset uses the extractive fallback. |
| `ML_LLM_MODEL` | No | Model name sent to that URL. Default `llama3.2`. |
| `ML_LLM_API_KEY` | No | Optional bearer token for `ML_LLM_URL`. |
| `SEARCH_MAX_LIMIT` | No | Most hits one search ranks. Default `100`. |
| `GALAXY_NODE_LIMIT` | No | Cap on `GET /galaxy`. Unset returns every stored node. |
| `COUNTRY_SNAPSHOT` | No | Country snapshot path. Default `data/country_snapshot.json`. |
| `TOPIC_COUNTRY_YEAR_DB` | No | Topic × country × year SQLite path. Default `data/topic_country_year.sqlite`. |
| `PYTHON_VERSION` | Set in the blueprint | `3.11.11`, matching CI. Not a secret. |

### Vercel env vars

| Variable | What it does |
|---|---|
| `NEXT_PUBLIC_API_URL` | Render origin, no `/api/v1` suffix. Empty or missing forces the sample. |
| `NEXT_PUBLIC_API_MOCK` | `1` forces the sample even when the URL is set. Leave unset in production. |
| `NEXT_PUBLIC_SEARCH_LIMIT` | Search page size. Default `20`. A `limit` query on `/search` overrides it. |
| `NEXT_PUBLIC_GALAXY_LIMIT` | Optional `limit` sent to `GET /galaxy`. Unset asks for the whole graph. |

### What caps the paper count

487 is not a cap. It is not a constant in the client, in `GET /galaxy`, or in the API. The live mock bundle is the 66-paper sample.

| Surface | Cap |
|---|---|
| Built-in sample | 66 papers (`FIXTURE_COUNT`). |
| `GET /search` | Ranks at most `SEARCH_MAX_LIMIT` (default 100), then pages with `limit` (default 20, clamped to 1..that cap) and `offset`. `total` is the size of that ranked window, not the corpus. A country or year filter over-fetches 5× the cap inside `ml.service.search`, then slices to the cap. |
| Web search page | Page size `NEXT_PUBLIC_SEARCH_LIMIT` or `?limit=`, plus `?offset=`. The pager shows “Showing a–b of total”. Changing the query or a filter clears `offset`. |
| `GET /api/v1/stats` | `{papers}` is `len(store)`, the indexed corpus. The nav shows this when the API is configured. |
| `GET /galaxy` | No paper limit unless `?limit=` or `GALAXY_NODE_LIMIT` is set. The client sends a limit only when `NEXT_PUBLIC_GALAXY_LIMIT` is set. `LINK_CAP = 200` in `ml/galaxy.py` is edges, not papers. |
| Related and similar | `limit` clamped to 1..50. |
| `GET /topic-country-years` | Default 1000, clamped to 1..10000. The countries and timeline pages request 5000. |
| Collaborations | Default `limit` 200. |
| Gaps, emerging, semantic gaps | 20, 20, and 10 inside `ml_bridge`. These are topic rows, not the corpus. |
| OpenAlex ingest | 200 works per page. `--max-records` default 50000. The first anonymous page of the search-eval fetch is 50 ids. |

## Open items
- [ ] #16 read gaps and emerging topics from the precomputed discoveries snapshot: reviewed, tests pass with main merged in (ml+pipeline 91, api 27, integration 42). The merge resolution changes `.github/workflows/v2-ingest.yml` (discover step + upload of the refreshed `discoveries.json` after `ml.cli update`), and the push was refused because the bot token lacks the `workflow` permission. Needs a token with Workflows read/write, or the owner pushes the merge. Until #16 lands, gap/emerging routes still compute live.
- [ ] `/galaxy` nodes are papers (#15). The hero used to say "Nodes are topics"; the galaxy-copy row above changes that wording. The client still normalises both payload shapes.
- [ ] First successful 1st/15th run of `python -m ml.cli index` against the real `works_v2.jsonl`. The workflow step is in place. `python -m ml.cli update` also runs discoveries and rebuilds the galaxy.
- [x] Live pgvector / Supabase: schema applied and 3000 works loaded on 2026-10-15 (see Live data under Deploy).
- [ ] Deploy the API from `render.yaml` (free tier) and set Vercel `NEXT_PUBLIC_API_URL` to that origin. The web app is already on Vercel and, with the URL unset, serves the 66-paper sample. Env vars are listed under Deploy above. Do not commit secret values.
