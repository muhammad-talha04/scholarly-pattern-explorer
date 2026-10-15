# UI audit — 2026-10-15

Reviewed `apps/web` in mock mode (`NEXT_PUBLIC_API_MOCK=1`) on a 1440×900 desktop and a 390×844 phone, before the UI v3 polish. Screenshots of that pass are in `docs/ui/before/`. The same routes after the fixes are in `docs/ui/after/`.

## What already worked
- Landing galaxy, search with filters, paper side panel (summary, ask, related, original link), countries globe with bars and arcs, timeline scrubber, and patterns (itemsets, rules, lifecycles, gaps) all render.
- The nav badge says `mock data` when the API is unset.
- The 2D toggle swaps the galaxy and the globe for SVG drawings.
- Search submits a trimmed query. Result cards show year, citations and match score.
- Keyboard focus rings existed on buttons and inputs. The paper panel closes.

## What looked dated
- One dark gradient and a system font across every page. Glass panels were the same rectangle everywhere, with little hierarchy.
- The galaxy was flat emissive spheres on a wire starfield. No bloom, and labels were painted on every large node, so the picture read as a diagram rather than a sky.
- The globe was a wireframe ball. Bars floated with no landmass, so a country was hard to place.
- Loading was a 20px spinner. Empty copy was one grey sentence (`None in this window`, `Type a question or topic to begin`).
- The timeline was only a bar chart of ingest runs. Patterns born and died did not connect to the topic volumes underneath.

## What was broken
1. **Hero over the labels.** The headline sat in the lower third of the galaxy, on top of the node labels. Confirmed at 1440px (`before/01-galaxy-desktop.png`).
2. **390px nav and search.** The logo, five links, the mock badge and the 3D toggle share one row, so the links run off the screen. The search field's long placeholder sets a min-content width, the row cannot shrink, and `overflow: hidden` on the hero clips the Search button (`before/07-galaxy-mobile.png`, `before/08-search-mobile.png`).
3. **No country outlines.** The 3D globe and the flat map draw bars and arcs only (`before/04-countries-desktop.png`).
4. **Counting toggle.** Only `fractional` and `full`. The API and the schema already accept `per_country`.
5. **Empty galaxy.** While patterns are loading, or when they come back empty, the canvas is not mounted. The page is the ink background plus the headline: a black void. `?preview=empty` now shows the designed state (`after/galaxy-empty.png`).
6. **Born and died panels.** Runs are dated 2026, so the panel always picks the 2025 pattern window. The old fixtures never start or stop in that window, so both lists say "None in this window" (`before/05-timeline-desktop.png`).

## Fixed in this change
- Headline and search sit in a card under the nav. Node labels appear on hover or focus, with a "Search this topic" action. The camera eases toward a focused topic. Bloom is on in 3D.
- Below the `lg` breakpoint the links move into a Menu button. The search field is `min-w-0` and the button is `shrink-0`. At 390px the Search button's right edge is inside the viewport (measured 352px on the galaxy, 371px on search) and the document does not scroll sideways. The three counting radios sit at x 17–259.
- Country borders come from Natural Earth 110m (`world-atlas` + `topojson-client`), as line segments on the sphere and as an equirectangular path in the 2D fallback. The date line is split so shapes do not streak across the map.
- The toggle is fractional / per country / full, with a sentence that says which rule is on screen. `per_country` changes collaboration weights. Country totals stay fractional unless the mode is `full`, which matches `pipeline/country_api.py`.
- An empty snapshot shows a titled empty state and a way forward (search, or a note that the country aggregate has not landed). The same pattern is used for search, runs, and a missing topic-year table.
- Pattern fixtures now include topics that are born in 2025 and topics that die in 2025. The timeline uses that window for a 2026 run, and if a year has no changes it says so and shows the latest window that does. The panels list real itemsets (`after/timeline-desktop.png`).
- Also in this pass: topic streamgraph, globe year slider, compare, collections, related-paper map, first-run tour, and the type/client hooks for `/galaxy` and `/topic-country-years`.

## Still on fixtures until a route exists
- `GET /api/v1/galaxy` is not on main. The client falls back and switches on the first 200.
- `GET /api/v1/topic-country-years` is talha's open PR #6. Same fallback. While the rest of the API is live and this route 404s, the streamgraph and the year slider stay in a waiting state instead of drawing fixture numbers on live countries.
