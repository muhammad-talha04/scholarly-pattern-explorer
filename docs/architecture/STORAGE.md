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

`paper_embeddings`

| column | type |
|---|---|
| `work_id` | text, primary key |
| `embedding` | `vector(384)` |
| `meta` | jsonb |
| `model` | text, nullable |

Index: `paper_embeddings_hnsw` on `embedding` with `vector_cosine_ops`.

`documents`

| column | type |
|---|---|
| `kind` | text, primary key |
| `payload` | jsonb, not null |
| `updated_at` | timestamptz, default `now()` |

DDL for a fresh database is in `pipeline/schema_v2.sql`. An existing database
gets the same objects from `pipeline/migrations/001_ml_storage.sql`.
`PgVectorStore` runs that migration when it connects. Each statement runs on
its own, including the block that drops `NOT NULL` on `paper_embeddings.model`
when an older `schema_v2.sql` created that column.

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

The typed topic × country × year aggregate from the country pipeline still
lives in SQLite `topic_country_year` (`data/topic_country_year.sqlite`, view
`topic_country_year_v`). The `documents` row of kind `topic_country_year` is
the shared JSON slot for the same counts.
