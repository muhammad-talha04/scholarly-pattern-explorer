# apps/web — Scholarly Pattern Explorer front end (owner: harry)

Next.js 14 (App Router) + TypeScript + Tailwind + react-three-fiber/drei + Framer Motion.
Pages talk only to the API (`/api/v1`, contracts in `apps/api/app/schemas.py`).

```bash
cd apps/web
cp .env.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8000
npm ci
npm run dev                  # http://localhost:3000
npm run lint && npm run typecheck && npm test && npm run build
```

## Structure
- `src/lib/api/types.ts`: TypeScript mirror of `schemas.py` (+ provisional `Counting`, `Collaboration`).
- `src/lib/api/client.ts`: typed client. Falls back to `mock.ts` fixtures when `NEXT_PUBLIC_API_URL`
  is empty, the API is unreachable, or a route returns 501. `NEXT_PUBLIC_API_MOCK=1` forces mocks.
  A badge in the nav shows `live` / `mock data`.
- `src/features/<name>/`: self-contained page modules: `galaxy` (landing), `search`, `countries`,
  `timeline`, `patterns`. `src/app/<route>/page.tsx` only mounts a feature.
- Low-power mode: `prefers-reduced-motion`, no WebGL, or the nav toggle switches every 3D view to an SVG fallback.

## Adding a page
Create `src/features/<name>/`, add an API method in `client.ts` (+ fixture in `mock.ts`), mount it in
`src/app/<name>/page.tsx` and add a link in `components/Nav.tsx`.
