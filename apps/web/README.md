# apps/web — Scholarly Pattern Explorer front end (owner: harry)

Next.js 14 (App Router) + TypeScript + Tailwind + react-three-fiber/drei + Framer Motion.
Pages talk only to the API (`/api/v1`, contracts in `apps/api/app/schemas.py`).
Libraries are free and open source. No paid APIs.

```bash
cd apps/web
cp .env.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8000
npm ci
npm run dev                  # http://localhost:3000
npm run lint && npm run typecheck && npm test && npm run build
```

`NEXT_PUBLIC_API_MOCK=1`, or an empty `NEXT_PUBLIC_API_URL`, forces the built-in sample. The nav then shows a Demo data badge and a one-line note. Sample papers open an OpenAlex title search, not a DOI. When `NEXT_PUBLIC_API_URL` points at the API, the badge shows the indexed count from `GET /api/v1/stats`. Search page size is `NEXT_PUBLIC_SEARCH_LIMIT` (default 20), or `?limit=` and `?offset=` on `/search`. `NEXT_PUBLIC_GALAXY_LIMIT` is optional; unset, the client asks `/galaxy` for every node.

## Pages
| Route | What it shows |
|---|---|
| `/` | Paper galaxy. Each dot is a paper. Colors and groups are topic clusters, so papers sit together by theme. A slow spin and a node pulse in 3D; an SVG drawing in 2D. `?preview=empty` shows the empty state. |
| `/search` | Meaning search, filters, paper panel (summary, ask, related-paper map, save, pin). |
| `/compare?a=&b=` | Two papers side by side. Pin them from search; the pair is kept in `sessionStorage`. |
| `/countries` | Globe with Natural Earth outlines, collaboration arcs, fractional / per country / full counting, and a year slider. |
| `/timeline` | Ingest runs, patterns born and died, topic streamgraph. |
| `/patterns` | Itemsets, derived rules, lifecycles, research gaps. |
| `/collections` | Collections stored in `localStorage` on this device. |

A first-run tour starts until it is dismissed (`spe-tour-done`). Replay it from Tour in the nav.

## Data that is still a fixture
| Client call | Route | Switches to live when |
|---|---|---|
| `api.galaxy()` | `GET /galaxy` | the route returns 200. Each node is a paper; cluster color and name are its topic group. Accepts `{ nodes, clusters, links }` and the #8 paper list `{ id, x, y, z, cluster_id, cluster_label, year }`. A paper list becomes nodes and clusters with empty links. Any other body becomes an empty graph, and the landing page shows its empty state. |
| `api.topicCountryYears()` | `GET /topic-country-years` | the route returns 200. Rows: `topic_id`, `topic_name`, `country_code`, `year`, `paper_count`, `fractional_count`. Optional filters: `topic_id`, `country`, `year`, `limit`. This is talha's PR #6. The timeline and country charts do not call it. |
| `api.publications()` | `GET /aggregates/publications` | the route returns 200. Not on the API yet (lura). Each bucket is `{key, sampled, estimated_total}`. Sampling is even per month, so the timeline plots `estimated_total` (labelled Estimated OpenAlex output) and the tooltip shows both numbers. A 404 leaves the chart waiting. Fixtures, including `?corpus=80k`, stand in until then. |
| `api.topicVolume()` | `GET /aggregates/topics` | the route returns 200. Points are `{key, share}`, the percent of that year or month. A column with papers sums to 100. An empty month is all zeros. A 404 leaves the stream waiting. |
| `api.countryChart()` | `GET /aggregates/countries` | the route returns 200 with `items` of `{code, name, share}` plus `other: {share, countries}`. `share` is the percent of the selected period. A 404 folds the precomputed `GET /countries` totals into those shares (top 12 + Other). It does not count rows. |
| `api.countries()` / `api.collaborations()` | already on main | a non-empty snapshot. An empty list is an empty state. `per_country` changes collaboration weights; country totals follow the fractional snapshot unless `counting=full`. The year slider reads `by_year` on that snapshot. |

A 404 on `/galaxy` or `/topic-country-years` uses fixtures for that call only. A 404 on `/aggregates/publications` or `/aggregates/topics` leaves those charts waiting, so fixture totals are not drawn on a live corpus. If `/aggregates/countries` is missing, the country chart turns the live `/countries` totals into a percent of the selected period (top 12 and Other). The year slider reads `by_year` on `/countries`.

## Structure
- `src/lib/api/types.ts`: TypeScript mirror of `schemas.py`, plus `GalaxyGraph` and `TopicCountryYear`.
- `src/lib/api/client.ts`: typed client. Falls back when the API is unset, unreachable, or returns 501.
- `src/features/<name>/`: page modules. `src/app/<route>/page.tsx` only mounts one.
- `src/lib/world.ts`: country outlines from `world-atlas` (Natural Earth, public domain) via `topojson-client`.
- Low-power mode: `prefers-reduced-motion`, no WebGL, or the nav toggle. Galaxy and globe both have an SVG fallback.

## Design
Colors live in `src/lib/palette.ts` (CSS variables plus `clusterColors`). The ground is deep navy `#0B0F1A` with an amber accent `#F5A54A`. Galaxy nodes are a small spaced set of warm amber spheres with a tight soft halo, spokes to a hub, and a dense field of pale-blue dust around them. Charts and the globe use the Okabe–Ito set. UI type is Space Grotesk, panels use the `glass` class, and the landing search uses `search-hero`. The audit of the previous UI is `docs/ui/AUDIT.md`.
