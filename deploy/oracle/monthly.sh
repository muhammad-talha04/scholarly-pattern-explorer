#!/usr/bin/env bash
# Monthly data update, run by cron on the 1st. Everything writes to /data, which the API
# reads, so patterns, gaps, emerging topics, countries and the run log all refresh
# (on Render they were frozen in committed snapshot files).
set -euo pipefail
cd "$(dirname "$0")"
echo "== $(date -u) monthly update"
git -C ../.. pull -q --ff-only || true
docker compose build -q api

run() { docker compose run --rm -T api sh -c "$1"; }

# First run: the live corpus (from Postgres) is the JSONL every later step appends to.
run '[ -s /data/works_live.jsonl ] || python -m ml.export_corpus --out /data/works_live.jsonl'

run 'set -e
  before=$(wc -l < /data/works_live.jsonl)
  set +e
  python -m pipeline.ingest --out /data/works_live.jsonl --state /data/ingest_state.json \
         --max-records 600 --sample-seed "$(date -u +%Y%m)"
  code=$?; set -e
  [ "$code" -eq 1 ] && exit 1
  tail -n +$((before + 1)) /data/works_live.jsonl > /data/new.jsonl
  echo "new works: $(wc -l < /data/new.jsonl)"
  if [ -s /data/country_snapshot.json ] && [ -s /data/new.jsonl ]; then
    python -m pipeline.country_stats --new /data/new.jsonl --prev /data/country_snapshot.json \
           --out /data/country_snapshot.json --corpus /data/works_live.jsonl
  fi
  python -m ml.cli index --jsonl /data/new.jsonl --max-db-mb 150000
  python -m ml.cli update --jsonl /data/works_live.jsonl'

docker compose restart api   # drop in-process caches so the new files are served
echo "== done $(date -u)"
