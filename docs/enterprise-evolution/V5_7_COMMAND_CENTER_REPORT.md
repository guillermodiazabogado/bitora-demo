# BITORA V5.7 Command Center Report

## SUMMARY

V5.7 implements a Command Center foundation as a read-only, event-scoped operational dashboard layer. It aggregates existing BITORA V4/V5 telemetry without changing V4 authority, V5.1 access enforcement, device sync behavior, entitlements, lead retrieval, vehicles, or production communications.

Feature flag:

- `command_center_v5`
- default: OFF

## ARCHITECTURE

The Command Center is an aggregation layer over existing modules:

- Access State Engine;
- Device Identity and Edge Sync;
- Entitlements and service points;
- Lead Retrieval;
- Vehicle and logistics;
- Domain events;
- Jobs and health signals.

It does not introduce a new operational truth. It reads the source modules, summarizes their status, and isolates failures per section.

## COMMAND CENTER SNAPSHOT

Snapshot schema:

- `overview`
- `access`
- `occupancy`
- `zones`
- `doors`
- `devices`
- `edge`
- `conflicts`
- `entitlements`
- `vehicles`
- `leads`
- `system_health`
- `alerts`

The snapshot contract is aggregated and avoids personal data and QR/token exposure.

## UI

V5.7 includes a dashboard foundation renderer for:

- top bar;
- operational cards;
- abstract event map;
- access flow;
- device cards;
- occupancy panel;
- alert panel.

Generated artifact:

- `docs/enterprise-evolution/V5_7_COMMAND_CENTER_DASHBOARD_FOUNDATION.html`

## ALERT ENGINE

Tables:

- `enterprise_alert_rules`
- `enterprise_operational_alerts`

Supported lifecycle:

- OPEN
- ACKNOWLEDGED
- RESOLVED

Supported severities:

- INFO
- WARNING
- CRITICAL

Initial alert families:

- Edge queue backlog;
- Edge conflict backlog;
- stale devices;
- occupancy warning;
- occupancy critical.

Alerts are deduplicated by event and active alert key.

## OCCUPANCY

V5.7 separates:

- access-counter occupancy;
- camera-counter occupancy.

Camera occupancy is explicitly `UNAVAILABLE` when no camera source is configured.

## FAILURE ISOLATION

Each section is evaluated independently. A failing module returns `UNAVAILABLE` for that section while the remaining dashboard sections continue to render.

## SECURITY

Controls verified:

- event scope;
- organization scope;
- no token leakage in snapshot;
- no participant email leakage in snapshot;
- no production changes;
- no V5 enforcement.

## BACKUP_RESTORE

Command Center tables are included in event backup and restore:

- alert rules;
- operational alerts.

## TEST_RESULTS

Dedicated verifier:

- `verificar_v5_7_command_center.py`

Result:

- PASS

Output artifacts:

- `docs/enterprise-evolution/V5_7_TEST_RESULTS.json`
- `docs/enterprise-evolution/V5_7_PERFORMANCE_BASELINE.json`

## NO_REGRESSION

V5.7 is additive and remains behind `command_center_v5`.

## ROLLBACK

Set:

- `command_center_v5 = OFF`

This stops use of the Command Center layer while preserving alerts/history for audit.

## NEXT_RECOMMENDED_EXECPLAN

V5.8 — Operational UI Integration & Admin Routes, only after human approval.
