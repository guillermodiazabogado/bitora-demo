#!/usr/bin/env bash
set -euo pipefail

candidate='/mnt/c/Users/Noxie-PC/.codex/worktrees/bitora-phase62-candidate/qr white label'
evidence='/mnt/c/Users/Noxie-PC/.codex/worktrees/bitora-qr-latency-phase-6-2/qr white label/auditoria/bitora_5_8_2_phase_6_3/evidence'
expected_sha='33c13cf0aaf79baae4e28d2603cb0732a10dbde2'

cd "$candidate"
actual_sha="$(git.exe rev-parse HEAD | tr -d '\r')"
test "$actual_sha" = "$expected_sha"
test -z "$(git.exe status --porcelain | tr -d '\r')"

for repetition in 1 2 3; do
  python3 scripts/capacity_benchmark.py \
    --report "$evidence/cycle3-gate1-24r-180s-r${repetition}.json" \
    --checkpoint "$evidence/cycle3-gate1-24r-180s-r${repetition}.checkpoint.json" \
    --levels 2 \
    --workers 25 \
    --duration-seconds 180 \
    --warmup-seconds 3 \
    --sample-seconds 5 \
    --max-operations 100 \
    --access-concurrency 24 \
    --access-mode valid \
    --postgres-access-concurrency 1
done
