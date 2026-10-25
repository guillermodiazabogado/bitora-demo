# BITORA V5.9 Production Runbook

## PRE-EVENT
1. Confirm event, organization, users, roles, activities and capacities.
2. Provision Event Edge and devices.
3. Generate signed Event Dataset.
4. Verify signature, stage and activate dataset.
5. Confirm Live Readiness is READY or READY_WITH_WARNINGS with accepted warnings only.
6. Run backup before opening operations.

## LIVE START
1. Start Edge.
2. Confirm local storage and clock status.
3. Confirm devices online or documented fallback state.
4. Enable live operation only for certified capabilities.

## CLOUD OUTAGE
1. Continue local operation for EDGE_LOCAL_SAFE capabilities.
2. Confirm persist-before-ACK queue is growing.
3. Do not activate unsigned or stale datasets.
4. Mark Cloud status degraded/offline in Command Center.

## EDGE OUTAGE
1. Stop Edge-dependent actions.
2. Use DEVICE_LOCAL_SAFE only where certified.
3. Restart Edge and verify queue recovery.

## RECONNECT
1. Sync batches.
2. Review conflicts.
3. Confirm queue depth returns to zero or only documented conflicts remain.
4. Run backup.

## POST-EVENT
1. Stop live intake.
2. Final sync and reconciliation.
3. Export reports.
4. Final backup and archive evidence.
