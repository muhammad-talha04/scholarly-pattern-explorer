#!/usr/bin/env bash
# Nightly compressed dump, keeps the last 7.
# ponytail: same disk as the database; copy to OCI Object Storage (10 GB free) for real off-box backups.
set -euo pipefail
cd "$(dirname "$0")"
f=/data/backups/spe-$(date -u +%F).dump
docker compose exec -T db pg_dump -U spe_api -d spe -Fc > "$f"
ls -1t /data/backups/spe-*.dump | tail -n +8 | xargs -r rm --
echo "$(date -u) $f $(du -h "$f" | cut -f1)"
