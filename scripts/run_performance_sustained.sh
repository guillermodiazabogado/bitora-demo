#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESULTS="${BITORA_PERF_RESULTS_DIR:-/opt/bitora-perf-results}"
mkdir -p "$RESULTS"
cd "$ROOT"

run_case() {
  local name="$1"
  shift
  printf '%s START %s\n' "$(date -u +%FT%TZ)" "$name"
  python3 scripts/capacity_benchmark.py \
    --report "$RESULTS/$name.json" \
    --checkpoint "$RESULTS/$name.checkpoint.json" \
    "$@"
  printf '%s PASS %s\n' "$(date -u +%FT%TZ)" "$name"
}

for repetition in 1 2 3; do
  run_case "registration-i2-w25-600s-r${repetition}" \
    --levels 2 --workers 25 --duration-seconds 600 --warmup-seconds 10 \
    --sample-seconds 10 --access-concurrency 12 --access-mode valid
done

for repetition in 1 2 3; do
  run_case "qr-valid-i2-r24-600s-r${repetition}" \
    --levels 2 --workers 25 --duration-seconds 600 --warmup-seconds 2 \
    --sample-seconds 10 --max-operations 100 --access-concurrency 24 --access-mode valid
done

for repetition in 1 2 3; do
  run_case "qr-antipassback-i2-r16-600s-r${repetition}" \
    --levels 2 --workers 25 --duration-seconds 600 --warmup-seconds 2 \
    --sample-seconds 10 --max-operations 100 --access-concurrency 16 --access-mode antipassback
done

printf '%s COMPLETE all sustained performance cases\n' "$(date -u +%FT%TZ)"
