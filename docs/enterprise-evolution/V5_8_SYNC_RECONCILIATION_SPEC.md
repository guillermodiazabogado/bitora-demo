# BITORA V5.8 Sync Reconciliation Spec

## Persistent Queue

V5.8 reuses enterprise_edge_queue. ACK to device is only returned after durable local commit.

## Sync

EDGE -> BATCH -> CLOUD -> ACK -> CHECKPOINT.

Supports idempotency, duplicate suppression, partial batch results and deterministic reconciliation.

## Conflicts

Conflicts are preserved in enterprise_edge_reconciliations. Offline double-spend is classified as REVIEW_REQUIRED, not hidden.

## Recovery

On reconnect Edge exchanges checkpoints, syncs pending operations, writes reconciliation evidence, then updates Edge status.
