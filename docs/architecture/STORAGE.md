# Embeddings and document storage

One store holds paper embeddings and JSON documents. The galaxy payload is one
of those documents. Topic counts, country counts, and pattern snapshots use the
same two methods.

## Which backend

| Variable | Effect |
|---|---|
| `DATABASE_URL` | When this is set, the store is Postgres with the `vector` extension (Supabase-compatible). |
| `ML_VECTOR_BACKEND` | `pgvector` forces Postgres and requires `DATABASE_URL`. `local` forces files even when `DATABASE_URL` is set. When the variable is unset, a `DATABASE_URL` selects Postgres and a missing `DATABASE_URL` selects files. |
| `ML_DATA_DIR` | Root of the file backend. Default `data/ml`, resolved from the repo root by `ml/paths.py`. |

File layout:

- embeddings: `{ML_DATA_DIR}/vectors/vectors.npy` and `{ML_DATA_DIR}/vectors/meta.json`
- documents: `{ML_DATA_DIR}/vectors/documents/{kind}.json`

Offline tests leave `DATABASE_URL` unset (or set `ML_VECTOR_BACKEND=local`) and use the files.

## Tables

Every Postgres table is created by a numbered file in `db/migrations/`. Apply them in order:

```bash
DATABASE_URL=postgresql://... python -m db.apply   # from the repo root
```

`PgVectorStore` runs the same files when it connects. Each statement is idempotent (`CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`, `ENABLE ROW LEVEL SECURITY`). Row level security is on and there are no policies, so the Supabase `anon` and `authenticated` roles cannot read or write. The API uses `DATABASE_URL`, and that role bypasses row level security.

| file | tables |
|---|---|
| `001_vector_storage.sql` | `vector` extension, `paper_embeddings`, `documents` |
| `002_topic_country_year.sql` | `topic_country_year`, view `topic_country_year_v` |
| `003_discovery_snapshots.sql` | `discovery_snapshots` |
| `004_runs_summaries_snapshots.sql` | `runs`, `paper_summaries`, `snapshots` |

`paper_embeddings`

| column | type |
|---|---|
| `work_id` | text, primary key |
| `embedding` | `vector(384)` |
| `meta` | jsonb |
| `model` | text, nullable |

Index: `paper_embeddings_hnsw` on `embedding` with `vector_cosine_ops`. An older `schema_v2.sql` created `model TEXT NOT NULL`; `001` drops that constraint when it is still present.

`documents`

| column | type |
|---|---|
| `kind` | text, primary key |
| `payload` | jsonb, not null |
| `updated_at` | timestamptz, default `now()` |

`topic_country_year`

| column | type |
|---|---|
| `topic_id` | varchar, primary key (with the next two) |
| `topic_name` | varchar |
| `country_code` | varchar |
| `year` | integer |
| `paper_count` | integer |
| `fractional_count` | double precision |

Primary key: `(topic_id, country_code, year)`. The view `topic_country_year_v` is `security_invoker` (Postgres 15, which Supabase provides), so it follows the table's row level security. `pipeline/country_stats.py` replaces this table when `use_postgres()` is true (the same rule as `get_store`: `DATABASE_URL` selects Postgres unless `ML_VECTOR_BACKEND=local`, and `ML_VECTOR_BACKEND=pgvector` forces Postgres). Otherwise it rewrites SQLite `data/topic_country_year.sqlite`. An explicit `--table` always writes SQLite, so a local run can keep a file even when `DATABASE_URL` is set. Each run replaces the full combined row set. The snapshot tally is what makes the update incremental, so a second run does not add those rows on top of the table again. `GET /api/v1/topic-country-years` reads the same table and falls back to the snapshot list when the SQLite file is missing or Postgres cannot be reached. `/countries` totals stay on the snapshot tally, because summing this table would count a multi-topic paper more than once.

`discovery_snapshots`

| column | type |
|---|---|
| `id` | bigserial, primary key |
| `run_date` | date, not null |
| `kind` | text, not null (`gap`, `emerging`, and later kinds) |
| `country_code` | text, optional |
| `results` | jsonb, not null |
| `created_at` | timestamptz, default `now()` |

Indexes: `discovery_snapshots_run_date_idx` on `run_date`; `discovery_snapshots_kind_country_date_idx` on `(kind, country_code, run_date DESC)`; `discovery_snapshots_created_at_idx` on `created_at DESC`.

`runs`, `paper_summaries`, and `snapshots` are the incremental-run tables that used to live only in `pipeline/schema_v2.sql`. That file now points here.

The DuckDB corpus (`works`, `topics`, and the mining tables) stays in `schema.sql` and `indexes.sql`. Those files are not part of this Postgres rebuild.

## Document kinds

| kind | payload |
|---|---|
| `galaxy` | body of `GET /api/v1/galaxy` |
| `galaxy_state` | frozen PCA basis and per-paper assignments |
| `patterns` | pattern snapshot |
| `countries` | country counts |
| `topics` | topic counts |
| `topic_country_year` | topic × country × year counts |

A kind name matches `^[a-z][a-z0-9_]{0,63}$`. The names above are the ones this
repo writes. Another kind can be stored the same way:

```python
from ml.store import get_store

store = get_store()
store.put_document("countries", {"PK": {"papers": 12}})
store.get_document("countries")
```

`python -m ml.cli index` and `python -m ml.cli update` rebuild `galaxy` and
`galaxy_state`. `GET /api/v1/galaxy` only reads the stored `galaxy` document.

The typed topic × country × year aggregate is the `topic_country_year` table.
`pipeline/country_stats.py` writes it to Postgres when `use_postgres()` is true
and to SQLite `data/topic_country_year.sqlite` (view `topic_country_year_v`)
otherwise. `--table` forces the SQLite file. The DDL is
`db/migrations/002_topic_country_year.sql`. The `documents` row of kind
`topic_country_year` is a separate JSON slot and is not what the country
pipeline writes.

Gap and emerging runs can be stored in `discovery_snapshots` (`kind` is `gap`
or `emerging`, `country_code` optional, `results` is the JSON payload).
