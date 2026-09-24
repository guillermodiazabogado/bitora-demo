#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEPLOY_DIR="${ROOT_DIR}/deployment/hetzner"

cd "${DEPLOY_DIR}"

if [[ ! -f ".env" ]]; then
  echo "Missing ${DEPLOY_DIR}/.env. Copy .env.example to .env and fill secrets first." >&2
  exit 1
fi

docker compose pull postgres caddy
docker compose build app worker
docker compose up -d
docker compose ps

echo "Waiting for BITORA health..."
for _ in {1..60}; do
  if docker compose exec -T app python -c "import urllib.request; urllib.request.urlopen('http://localhost:8787/health', timeout=5).read()" >/dev/null 2>&1; then
    echo "BITORA app health: OK"
    exit 0
  fi
  sleep 5
done

echo "BITORA app health did not become ready in time." >&2
docker compose logs --tail=100 app
exit 1
