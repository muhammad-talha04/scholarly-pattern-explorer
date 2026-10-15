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

`NEXT_PUBLIC_API_MOCK=1`, or an empty `NEXT_PUBLIC_API_URL`, forces fixtures. The nav badge reads `live` or `mock data`.

## Pages
| Route | What it shows |
|---|---|
| `/` | Topic galaxy. Bloom and a camera move in 3D; an SVG drawing in 2D. `?preview=empty` shows the empty state. |
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
| `api.galaxy()` | `GET /galaxy` | the route returns 200. Accepts `{ nodes, clusters, links }` and the #8 paper list `{ id, x, y, z, cluster_id, cluster_label, year }`. A paper list becomes nodes and clusters with empty links. Any other body becomes an empty graph, and the landing page shows its empty state. |
| `api.topicCountryYears()` | `GET /topic-country-years` | the route returns 200. Rows: `topic_id`, `topic_name`, `country_code`, `year`, `paper_count`, `fractional_count`. Optional filters: `topic_id`, `country`, `year`, `limit`. This is talha's PR #6. |
| `api.countries()` / `api.collaborations()` | already on main | a non-empty snapshot. An empty list is an empty state. `per_country` changes collaboration weights; country totals follow the fractional snapshot unless `counting=full`. |

A 404 on `/galaxy` or `/topic-country-years` uses fixtures for that call only. The year slider and the streamgraph stay off when the rest of the API is live and that table is missing, so fixture rows are not drawn on top of live countries.

## Structure
- `src/lib/api/types.ts`: TypeScript mirror of `schemas.py`, plus `GalaxyGraph` and `TopicCountryYear`.
- `src/lib/api/client.ts`: typed client. Falls back when the API is unset, unreachable, or returns 501.
- `src/features/<name>/`: page modules. `src/app/<route>/page.tsx` only mounts one.
- `src/lib/world.ts`: country outlines from `world-atlas` (Natural Earth, public domain) via `topojson-client`.
- Low-power mode: `prefers-reduced-motion`, no WebGL, or the nav toggle. Galaxy and globe both have an SVG fallback.

## Design
Tokens live in `tailwind.config.ts` and `src/app/globals.css` (`ink`, `accent`, `gap`, `glow`, `mist`). Display type is Fraunces, UI type is Space Grotesk, panels use the `glass` class. The audit of the previous UI is `docs/ui/AUDIT.md`.
