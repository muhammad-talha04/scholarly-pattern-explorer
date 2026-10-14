# Workflow design

## Data flow
```mermaid
flowchart LR
  OA[OpenAlex API] -->|1st and 15th, GitHub Actions| ING[pipeline/ingest.py<br/>only new works + 7-day overlap]
  ING --> JSONL[data/works_v2.jsonl]
  JSONL --> CS[pipeline/country_stats.py<br/>fractional + full counting]
  JSONL --> ML[ml/ package<br/>embeddings, summaries, incremental FP-Growth]
  CS --> SNAP[(snapshots per run)]
  ML --> DB[(Postgres + pgvector)]
  ML --> SNAP
  DB --> API[apps/api FastAPI /api/v1]
  SNAP --> API
  API --> WEB[apps/web Next.js + React Three Fiber]
```

## Team workflow
```mermaid
flowchart LR
  B[branch per owner] --> PR[draft PR against main]
  PR --> T[CI + Ami's cross-PR tests]
  T --> R[review by API owner if schemas.py changes]
  R --> M[Prince merges]
  M --> S[owner updates docs/STATUS.md]
```

Rules: build only against `apps/api/app/schemas.py`; one owner per folder;
never rebuild patterns from scratch, always merge onto the last snapshot;
every PR updates `docs/STATUS.md`.
