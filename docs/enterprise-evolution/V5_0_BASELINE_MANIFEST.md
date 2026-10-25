# BITORA V5.0 Baseline Manifest

Baseline: V5.0.1 gate closure before V5.1 Access State Engine Shadow.

## Git

- Branch: `deployment/v4-online`
- HEAD: `73a76cb55102048cb05deba8543cfc0d9f73d690`
- Working tree: dirty with V5.0 implementation, V5.0.1 test/tooling corrections, generated reports, and preexisting `R2_RESTORE_ISOLATED_VALIDATION.json` modification.
- External material removed from BITORA tree: Viviendas Roca / Sorteo QR files were moved to `C:\Users\Noxie-PC\Documents\BITORA_EXTERNAL_ARTIFACTS\qr-viviendas-roca`.

## V5.0 Scope

- Feature flag: `enterprise_core_model`, default OFF.
- Migration: `backend/migrations/036_v5_0_enterprise_core_shadow.sql`.
- Service: `backend/services/enterprise_core.py`.
- Tables: `enterprise_entities`, `enterprise_identities`, `enterprise_credentials`, `enterprise_doors`, `enterprise_devices`, `enterprise_entitlements`, `enterprise_rules`, `enterprise_domain_events`.

## Tested Engines And Storage

- Local regression DB engine: SQLite temporary databases created by the verification scripts.
- Staging endurance target: Railway URL documented in endurance metadata.
- Staging storage: R2 checks documented by the active endurance artifacts.

## Gate Results

| Gate | Result | Evidence |
| --- | --- | --- |
| `verificar_v4.py` | PASS | Legacy copy assertion updated to current participant portal shell; fixture now accredits before testing required activity without reservation; backup audit action updated to current `backup.event_created`. |
| `verificar_participant_experience_v4_0_3.py` | PASS | Portal event scope check updated to current case-insensitive token lookup and event/accreditation scoped queries. |
| `scripts/secret_scan.py` | PASS | External Viviendas Roca artifacts separated from BITORA tree; no secrets detected. |
| `verificar_v5_0_enterprise_core_shadow.py` | PASS | Confirms feature flag OFF, shadow model, idempotent backfill, mapping, entitlements, rules, doors, devices, domain events, multievent and backup/restore. |

Full machine-readable results: `docs/enterprise-evolution/V5_0_1_GATE_RESULTS.json`.

## Regression Suite

All existing applicable scripts passed:

- `verificar_v4.py`
- `verificar_v4_1_attendance_domain.py`
- `verificar_v4_2_attendance_closure_eligibility.py`
- `verificar_v4_3_certificates_foundation.py`
- `verificar_v4_4_surveys_foundation.py`
- `verificar_v4_5_speakers_foundation.py`
- `verificar_v4_6_zone_permissions_foundation.py`
- `verificar_v4_7_history_autocomplete_foundation.py`
- `verificar_v4_8_operations_center.py`
- `verificar_v4_9_communications_automation.py`
- `verificar_v4_10_analytics_functional_closure.py`
- `verificar_backup_restore.py`
- `verificar_multievent_isolation_20_events.py`
- `verificar_seguridad_basica.py`
- `verificar_participant_experience_v4_0_3.py`
- `verificar_v5_0_enterprise_core_shadow.py`
- `scripts/secret_scan.py`

## Protected V4 Contracts

- `/api/portal?token=`
- `/api/qr.svg?token=`
- `/api/validate`
- `/api/accreditations`
- `/api/register`
- `accreditations.token`
- `event_id`
- `person_id`
- `accreditation_id`
- CSV/JSON exports
- backup ZIP

## Portal Event Scope

Status: SAFE based on static source verification and regression tests.

Evidence:

- Portal payload resolves participant by `WHERE lower(a.token) = lower(?)`.
- Portal communications and surveys are scoped with `person_id` plus `event_id`.
- Published activities and announcements are scoped by `event_id`.
- Attendance/certificate data is scoped by `accreditation_id`.
- `verificar_multievent_isolation_20_events.py` passed.

## Secret Scan

Status: PASS.

The prior finding was caused by untracked external QR/Viviendas Roca assets mixed into the BITORA workspace. They were moved out of the product tree instead of adding broad scanner exclusions.

## Endurance

Run: `ENDURANCE-RAILWAY-R2-24H-20260924-213816`.

Status: RUNNING.

Available artifact evidence at inspection:

- `RUN_METADATA.json`: present.
- `HEARTBEAT.json`: status `RUNNING`, elapsed `9.977` hours, expected completion `2026-09-25T21:38:17-03:00`.
- `CHECKPOINTS.jsonl`: 61 lines.
- `FUNCTIONAL_CHECKS.jsonl`: 61 lines.
- `R2_CHECKS.jsonl`: 60 lines.
- `BACKUP_CHECKS.jsonl`: 2 lines.
- `ERRORS.jsonl`: not present.
- `FINAL_REPORT.md`: not present.

Endurance is not declared PASSED in this baseline because it had not completed and had no final verifier/report at inspection time.

## Golden Access Dataset

- Path: `docs/enterprise-evolution/V5_0_GOLDEN_ACCESS_DATASET.json`
- Cases: 10
- Purpose: compare V4 Access Engine decisions against V5.1 Access State Engine Shadow.

## Exclusions

No test gate was excluded. All three problematic gates are PASS after investigation and narrow correction.

## Open Risks

- Endurance remained RUNNING at baseline inspection; final result must be checked after expected completion.
- Working tree is not clean because V5.0/V5.0.1 changes are local and uncommitted.
- `R2_RESTORE_ISOLATED_VALIDATION.json` was already modified before this closure and was not changed by the gate fixes.
- Portal scope was verified by source/static regression plus multievent suite; no new destructive live cross-tenant test was added in this phase.

## V5.1 Readiness

GO for `V5.1 — ACCESS STATE ENGINE SHADOW`, with Endurance tracked separately until final completion.
