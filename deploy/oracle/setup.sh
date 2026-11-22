#!/usr/bin/env bash
# One-time server setup for an Oracle Always Free Ampere A1 VM (Ubuntu 22.04/24.04, arm64).
# Paste deploy/oracle/cloud-init.sh into "Initialization script" when creating the VM,
# or run by hand:  sudo BRANCH=main bash setup.sh
# Safe to re-run. Log: /var/log/spe-setup.log
set -euo pipefail
exec > >(tee -a /var/log/spe-setup.log) 2>&1

REPO=${REPO:-https://github.com/muhammad-talha04/scholarly-pattern-explorer.git}
BRANCH=${BRANCH:-main}
APP=/opt/spe
ORACLE=$APP/deploy/oracle

echo "== packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y docker.io docker-compose-v2 git curl cron iptables-persistent unattended-upgrades fail2ban
systemctl enable --now docker cron fail2ban

echo "== firewall: Oracle's Ubuntu image rejects everything but SSH in iptables"
for p in 80 443; do
  iptables -C INPUT -p tcp --dport $p -j ACCEPT 2>/dev/null || iptables -I INPUT 1 -p tcp --dport $p -j ACCEPT
done
netfilter-persistent save

echo "== code"
if [ -d $APP/.git ]; then git -C $APP fetch -q origin "$BRANCH" && git -C $APP checkout -q -B "$BRANCH" "origin/$BRANCH"
else git clone -q --depth 20 -b "$BRANCH" "$REPO" $APP; fi

echo "== data dirs (seeded from the committed snapshots the first time)"
mkdir -p /data/pg /data/app /data/caddy /data/backups
[ -d /data/app/ml ] || cp -r $APP/deploy/data/ml /data/app/ml
[ -f /data/app/country_snapshot.json ] || cp $APP/deploy/data/country_snapshot.json /data/app/

echo "== .env"
if [ ! -f $ORACLE/.env ]; then
  IP=$(curl -fsS https://api.ipify.org)
  cat > $ORACLE/.env <<EOF
PG_PASSWORD=$(openssl rand -hex 24)
API_DOMAIN=${API_DOMAIN:-${IP//./-}.sslip.io}
ALLOWED_ORIGINS=https://scholarly-pattern-explorer.vercel.app,https://scholarly-pattern-explorer-muhammad-talha04.vercel.app,http://localhost:3000
API_WORKERS=3
EOF
  chmod 600 $ORACLE/.env
fi

echo "== start"
cd $ORACLE
docker compose up -d --build
docker compose exec -T api python -m db.apply

echo "== cron: monthly data update (1st, 03:00 UTC) and nightly backup"
cat > /etc/cron.d/spe <<EOF
0 3 1 * * root $ORACLE/monthly.sh >> /var/log/spe-monthly.log 2>&1
30 2 * * * root $ORACLE/backup.sh >> /var/log/spe-backup.log 2>&1
EOF

echo "== done. API: https://$(grep API_DOMAIN .env | cut -d= -f2)/api/v1/health"
echo "   next: sudo $ORACLE/migrate.sh   (copies the data from Supabase)"
