# BITORA V5.8 Failure Matrix

| Scenario | Expected Result |
|---|---|
| NORMAL | Cloud + Edge operate normally |
| CLOUD_DOWN | Edge continues EDGE_LOCAL_SAFE operations |
| CLOUD_RECONNECT | Batch sync + reconciliation |
| EDGE_DOWN | Event operation CRITICAL unless Device Local certified |
| EDGE_RECOVERY | Queue preserved, sync resumes |
| DEVICE_DISCONNECT | Device stale/offline, no global failure |
| DUPLICATE_OPERATION | Idempotency suppresses duplicate |
| OUT_OF_ORDER | Device sequence preserved for reconciliation |
| STALE_DATASET | Conflict/review according to policy |
| EXPIRED_DATASET | Readiness NOT_READY for affected capabilities |
| REVOKED_DEVICE | Sync/auth denied |
| QUEUE_BACKLOG | Command Center Edge awareness reports pending sync |
| PARTIAL_SYNC_FAILURE | Failed operation isolated; batch can continue |
