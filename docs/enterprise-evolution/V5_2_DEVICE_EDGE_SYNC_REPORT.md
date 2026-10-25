# BITORA V5.2 Device Identity & Edge Sync Foundation Report

## SUMMARY

V5.2 implements the foundation for server-authoritative device identity and edge sync. It does not replace `/api/validate`, does not enable V5 enforcement, and does not introduce hardware drivers. The architecture follows server-authoritative persistent queues plus append-only access events and deterministic reconciliation.

## ARCHITECTURE

Target flow:

- BITORA Cloud remains authoritative.
- Edge/Device receives an event access dataset.
- Offline operations are persisted in a queue.
- On reconnect, operations are authenticated, deduplicated, reconciled and acknowledged per operation.

No CRDT, Kafka, RabbitMQ, Redis, hardware driver or multi-master design was introduced.

## DEVICE_IDENTITY

Implemented on top of `enterprise_devices`.

Device types supported:

- `ACCESS_TERMINAL`
- `RECEPTION_TERMINAL`
- `KIOSK`
- `HANDHELD`
- `EDGE_NODE`
- future-compatible generic types for printer/scanner/turnstile/camera/NFC/RFID.

Administrative states:

- `PROVISIONED`
- `ACTIVE`
- `SUSPENDED`
- `REVOKED`

Offline is treated as derived from heartbeat/last_seen, not as a persistent administrative state.

## DEVICE_AUTHENTICATION

PASS. Devices receive cryptographic provisioning secrets. Only credential hashes and hints are stored. Secrets can be rotated and devices can be revoked. Revoked devices cannot sync.

## CAPABILITIES

Implemented as declarative device capabilities, distinct from user permissions and participant entitlements.

Initial capabilities include:

- `VALIDATE_ACCESS`
- `CHECK_IN`
- `CHECK_OUT`
- `SCAN_QR`
- `PRINT_BADGE`
- `REGISTER`
- `VIEW_PARTICIPANT`
- `CONSUME_ENTITLEMENT`
- `SYNC_DATASET`

## EDGE_NODE

Implemented as `EDGE_NODE` device type. It can receive datasets, hold a queue, heartbeat, and sync operations.

## DATASET_MODEL

Implemented `ACCESS_FULL` event dataset.

Included:

- event identity;
- credential hashes/hints and status;
- revocations;
- doors;
- zones;
- entitlements;
- rules;
- stale policy/config.

Excluded by default:

- email;
- phone;
- documents;
- survey data;
- communications;
- internal notes.

## DATA_MINIMIZATION

PASS. Dataset verification confirms no email/phone fields are exported in the access dataset.

## DATASET_REVISION

PASS. Revision is deterministic from canonical JSON checksum:

- `event-<event_id>-<checksum-prefix>`

Dataset status can be:

- `CURRENT`
- `STALE`
- `UNKNOWN`

## PERSISTENT_QUEUE

PASS. Implemented `enterprise_edge_queue` with persisted operation ID, idempotency key, correlation ID, device sequence, payload, local decision, dataset revision, retry/status fields and server result.

Queue survives DB reopen/restart simulation.

## LOCAL_ACCESS

PASS. Local edge evaluation supports credential hash lookup, status, revocation check and `ALLOW`/`DENY` local decisions for access simulation. It is not wired to replace V4 cloud enforcement.

## SYNC_PROTOCOL

Implemented internal contracts:

- generate dataset;
- queue operation;
- sync batch;
- reconcile operation;
- heartbeat;
- telemetry.

## IDEMPOTENCY

PASS. Re-sending the same `idempotency_key` returns duplicate handling and does not apply a second logical access.

## ORDERING

PASS foundation. Queue stores `device_sequence` and reconciliation keeps sequence metadata. Gap policy is not blocking in V5.2.

## RECONCILIATION

PASS. Cloud authenticates the device, validates scope and dataset revision, evaluates server-side state, compares local/server decisions, classifies conflicts, and records reconciliation.

## CONFLICTS

Implemented classifications:

- `NO_CONFLICT`
- `DUPLICATE`
- `STALE_DATASET`
- `REVOCATION_CONFLICT`
- `ANTI_PASSBACK_CONFLICT`
- `STATE_CONFLICT`
- `RULE_CONFLICT`
- `UNKNOWN_CREDENTIAL`
- `DEVICE_REVOKED`
- `EVENT_SCOPE_ERROR`

## ACCESS_STATE_BOOTSTRAP

PASS. V5.2 adds idempotent bootstrap from reliable V4 state:

- `checked_in_at` creates an `INSIDE` snapshot.
- ambiguous state is not invented.

Golden after bootstrap:

- V4 matches: 10/10
- V5 matches: 10/10
- divergences: 0

## CONNECTIVITY_TESTS

PASS in simulation:

- online provisioning/auth;
- offline queue creation;
- restart durability via DB reopen;
- reconnect sync;
- duplicate resend;
- stale dataset conflict;
- multi-device conflict.

## PERFORMANCE

Measured locally with SQLite temp DB only. These numbers are not production capacity claims.

See `docs/enterprise-evolution/V5_2_PERFORMANCE_BASELINE.json`.

## SECURITY

PASS. Implemented device auth, credential rotation, credential revocation, organization/event scope checks, capability checks, idempotency replay protection, no plaintext secret persistence, and no secrets in domain event metadata.

## BACKUP_RESTORE

PASS. V5.2 tables are included in event backup/restore and verified by `verificar_v5_2_device_edge_sync_foundation.py`.

## MULTITENANT

PASS. A device scoped to Organization A / Event A cannot authenticate against another event or organization.

## TEST_RESULTS

Dedicated verifier:

- `verificar_v5_2_device_edge_sync_foundation.py`: PASS

No-regression:

- `verificar_v4.py`: PASS
- `verificar_participant_experience_v4_0_3.py`: PASS
- `verificar_multievent_isolation_20_events.py`: PASS
- `verificar_backup_restore.py`: PASS
- `verificar_seguridad_basica.py`: PASS
- `verificar_v4_6_zone_permissions_foundation.py`: PASS
- `verificar_v5_0_enterprise_core_shadow.py`: PASS
- `verificar_v5_1_access_state_engine_shadow.py`: PASS
- `verificar_v5_2_device_edge_sync_foundation.py`: PASS
- `scripts/secret_scan.py`: PASS

Machine-readable output:

- `docs/enterprise-evolution/V5_2_TEST_RESULTS.json`

## NO_REGRESSION

PASS.

## RISKS

- V5.2 remains foundation/simulation, not real event hardware deployment.
- No hardware drivers were implemented.
- No V5 enforcement was enabled.
- Sync batch performance test used empty batches for 100/1000 baseline shape, not production-scale real payloads.
- Edge physical backup/export is documented conceptually but not packaged as a standalone installer.
- Gap detection is stored via sequence metadata but not blocking.
- Rate limiting is not separately implemented in V5.2.
- Endurance V4 remains separate and still lacks final report in inspected artifacts.

## ROLLBACK

Set:

- `device_identity = OFF`
- `edge_sync = OFF`

Rollback keeps Cloud V4/V5.1 working and preserves device, queue, reconciliation and domain event history.

## NEXT_RECOMMENDED_EXECPLAN

V5.3 — Delegation & Company Portal.
