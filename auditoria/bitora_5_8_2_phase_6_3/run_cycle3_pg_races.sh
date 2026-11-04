#!/usr/bin/env bash
set -euo pipefail

network='bitora-p63-race-cycle3'
postgres='bitora-p63-race-pg'
cleanup() {
  docker rm -f "$postgres" >/dev/null 2>&1 || true
  docker network rm "$network" >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup
docker network create "$network" >/dev/null
docker run -d --name "$postgres" --network "$network" \
  -e POSTGRES_DB=bitora -e POSTGRES_USER=bitora \
  -e POSTGRES_PASSWORD=race-temporary postgres:16-alpine >/dev/null
for _ in $(seq 1 60); do
  if docker exec "$postgres" pg_isready -U bitora -d bitora >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
docker run --rm --network "$network" \
  -e QR_DB_ENGINE=postgres \
  -e QR_POSTGRES_DSN="postgresql://bitora:race-temporary@${postgres}:5432/bitora" \
  -e QR_POSTGRES_ACCESS_CONCURRENCY=2 \
  --entrypoint python bitora-phase63-cycle3:test verificar_p2_access_race_matrix.py
