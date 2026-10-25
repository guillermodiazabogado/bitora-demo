# BITORA V5.1 Access State Engine Shadow Report

## SUMMARY

V5.1 implements an additive Access State Engine in shadow mode. V4 remains the only real enforcement authority for `/api/validate`. When `access_state_engine_shadow` is OFF there is no observable runtime change. When ON, V5.1 evaluates the same access context, records append-only access events, compares V4 and V5 decisions, and keeps the V4 response untouched.

## ARCHITECTURE

Flow:

1. V4 `AccessValidationService` computes the real decision.
2. `/api/validate` returns the V4 decision.
3. If `access_state_engine_shadow` is enabled, V5.1 evaluates in parallel inside an isolated `try/except`.
4. V5.1 records comparison telemetry and domain events.
5. Any V5.1 exception is classified as `V5_ERROR` and does not break V4.

## STATE MODEL

Implemented states:

- `OUTSIDE`
- `INSIDE`

Implemented transitions:

- `ENTRY`: `OUTSIDE -> INSIDE`
- `EXIT`: `INSIDE -> OUTSIDE`

The state snapshot is derived from append-only V5.1 access events.

## ACCESS EVENT MODEL

New append-only event table:

- `enterprise_access_events`

Fields include organization, event, entity, credential, accreditation, door, zone, device, direction, decision, reason code, previous/proposed state, correlation, idempotency and metadata.

## FEATURE FLAGS

- `enterprise_core_model`: unchanged, default OFF.
- `access_state_engine_shadow`: added, default OFF.
- `access_state_engine_enforced`: defined as inert and always false in V5.1.

## V4/V5 COMPARATOR

New table:

- `enterprise_access_comparisons`

Comparison classes:

- `MATCH_ALLOW`
- `MATCH_DENY`
- `DIVERGENCE_V4_ALLOW_V5_DENY`
- `DIVERGENCE_V4_DENY_V5_ALLOW`
- `V5_ERROR`

## GOLDEN DATASET RESULTS

Input:

- `docs/enterprise-evolution/V5_0_GOLDEN_ACCESS_DATASET.json`

Output:

- `docs/enterprise-evolution/V5_1_GOLDEN_ACCESS_COMPARISON.json`

Results:

- Total cases: 10
- V4 expected matches: 10
- V5 matches: 8
- V5 divergences: 2

## DIVERGENCES

| Case | V4 | V5 | Classification | Reason |
| --- | --- | --- | --- | --- |
| `access.reentry_blocked` | rejected | ALLOW | EXPECTED_DIVERGENCE | V4 has legacy checked-in state; V5.1 shadow only uses V5 append-only state unless a V5 access event exists. |
| `access.activity_duplicate_entry` | rejected | ALLOW | EXPECTED_DIVERGENCE | V4 checks legacy activity access logs; V5.1 does not yet import historical V4 activity entries into V5 state. |

No unexplained divergence remains.

## ANTI_PASSBACK

PASS. V5.1 rejects a second `ENTRY` while the V5 state snapshot is already `INSIDE`.

## COOLDOWN

PASS. V5.1 supports context-provided cooldown seconds and returns `DENY / COOLDOWN` when the next transition is too early.

## REVOCATION

PASS. V5.1 supports credential revocation without deleting credentials or history. A revoked credential returns `DENY / REVOKED` in shadow.

## ENTITLEMENTS_AND_RULES

PASS. V5.1 evaluates Enterprise entitlements by type, scope, validity and status. The minimal rules evaluator supports time window, door, zone and accreditation state checks without `eval` or arbitrary code execution.

## ZONES_AND_DOORS

PASS. V5.1 accepts optional `door_id` and `zone_id`, verifies active scoped doors, and can evaluate zone-scoped entitlements and rules.

## IDEMPOTENCY

PASS. Access events and comparison rows support idempotency keys. Repeating the same access event idempotency key does not create a duplicate transition.

## TELEMETRY

PASS. Minimal telemetry is available from `AccessStateEngine.telemetry`, including total evaluations, V4/V5 allow/deny counts, matches, divergences, V5 errors, anti-passback, cooldown, revocation, entitlement denials and rule denials.

## PERFORMANCE

NOT DOCUMENTED. No stable latency baseline was captured in this ExecPlan.

## BACKUP_RESTORE

PASS. V5.1 tables were added to event backup/restore and verified by `verificar_v5_1_access_state_engine_shadow.py`.

## SECURITY

PASS. V5.1 is scoped by `organization_id` and `event_id`, uses correlation IDs, supports idempotency, avoids full token logging in V5 persistence, and isolates failures from V4 enforcement.

## TEST_RESULTS

Dedicated verifier:

- `verificar_v5_1_access_state_engine_shadow.py`: PASS

No-regression gate:

- `verificar_v4.py`: PASS
- `verificar_participant_experience_v4_0_3.py`: PASS
- `verificar_multievent_isolation_20_events.py`: PASS
- `verificar_backup_restore.py`: PASS
- `verificar_seguridad_basica.py`: PASS
- `verificar_v4_6_zone_permissions_foundation.py`: PASS
- `verificar_v5_0_enterprise_core_shadow.py`: PASS
- `verificar_v5_1_access_state_engine_shadow.py`: PASS
- `scripts/secret_scan.py`: PASS

Machine-readable test output:

- `docs/enterprise-evolution/V5_1_TEST_RESULTS.json`

## NO_REGRESSION

PASS. The required V4/V5.0 gates passed after V5.1.

## RISKS

- V5.1 is shadow only; V5 enforcement is intentionally not implemented.
- Historical V4 checked-in/activity state is not automatically imported into V5 state snapshots.
- Device authentication and Edge Sync are not implemented.
- Performance is not documented with a stable benchmark.
- V5.1 telemetry is service-level, not a Command Center UI.
- Endurance Railway/R2 remains a separate V4/staging run and was not declared PASS here.

## ROLLBACK

Set `access_state_engine_shadow = OFF`.

Rollback keeps:

- V4 `/api/validate` operational.
- V5 access events.
- V5 comparison records.
- Domain event evidence.
- Audit history.

## NEXT_RECOMMENDED_EXECPLAN

V5.2 — Device Identity & Edge Sync Foundation.
