#!/usr/bin/env bash
# Copy every row from Supabase into the local Postgres. Run once:  sudo ./migrate.sh
# Asks for the Supabase session-pooler URL (Project > Connect > Session pooler, port 5432).
# The URL is read from the terminal and never written to disk.
set -euo pipefail
cd "$(dirname "$0")"

read -rsp "Supabase connection string (postgresql://postgres.<ref>:<password>@...:5432/postgres): " SRC; echo
[ -n "$SRC" ] || { echo "empty"; exit 1; }

psql_local() { docker compose exec -T db psql -v ON_ERROR_STOP=1 -U spe_api -d spe "$@"; }

echo "== empty target tables, drop the vector index while loading (much faster)"
psql_local -c "TRUNCATE paper_embeddings, documents, sampling_rates, paper_summaries,
               topic_country_year, discovery_snapshots, snapshots, runs RESTART IDENTITY CASCADE;
               DROP INDEX IF EXISTS paper_embeddings_hnsw;"

echo "== copy data (about 450 MB, a few minutes)"
docker compose exec -T -e SRC="$SRC" db sh -c \
  'pg_dump "$SRC" --data-only --no-owner --no-privileges -n public' \
  | sed -e 's/extensions\.halfvec/halfvec/g' \
  | psql_local -q

echo "== rebuild the HNSW index and statistics"
psql_local -c "SET maintenance_work_mem='2GB'; SET max_parallel_maintenance_workers=3;
               CREATE INDEX paper_embeddings_hnsw ON paper_embeddings USING hnsw (embedding halfvec_cosine_ops);
               ANALYZE;"
psql_local -c "SELECT model, count(*) FROM paper_embeddings GROUP BY model;"

docker compose restart api
echo "== done"
