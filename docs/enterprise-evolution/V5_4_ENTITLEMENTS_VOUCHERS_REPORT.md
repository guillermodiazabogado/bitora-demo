# V5.4 Entitlements & Vouchers Report

## SUMMARY

V5.4 makes `enterprise_entitlements` operational for rights, benefits, vouchers, and consumption tracking. It preserves the single legacy QR model: the existing credential identifies the person/entity and BITORA checks entitlements behind it.

## DOMAIN_MODEL

The model separates Entitlement, optional Voucher representation, and Consumption. Entitlements define rights, Service Points define where benefits are consumed, and Consumptions are append-only facts.

## ENTITLEMENT_TYPES

`enterprise_entitlement_types` defines event-scoped benefit types such as MEAL, COFFEE, KIT, GIFT, PARKING, HOSPITALITY, SESSION, VIP, and custom event-safe codes.

## CONSUMABLE_NON_CONSUMABLE

Consumable entitlements track allocated, consumed, and available counts. Non-consumable entitlements remain active rights without incrementing consumed.

## GRANTS

The grant engine supports individual grants, bulk grants, idempotency, source/source_reference, validity windows, scope, and audit/domain events.

## COMPANY_DELEGATION_INTEGRATION

V5.4 integrates with V5.3 by granting benefits to all members of a Company or Delegation without confusing V5.3 registration quotas with V5.4 entitlements.

## SERVICE_POINTS

`enterprise_service_points` models buffet desks, coffee stations, kit desks, lounges, parking gates, and future device-bound service points.

## CONSUMPTION_ENGINE

`consume()` resolves credential/entity, checks entitlement status, validity, scope, service point, quantity, device capability, idempotency, records append-only consumption, updates entitlement counters, and emits domain events.

## ATOMICITY

Consumable updates use conditional database updates so the final available unit cannot be accepted twice by Cloud authority.

## IDEMPOTENCY

Consumption idempotency is enforced by `organization_id + idempotency_key`, returning duplicate results without creating another logical consumption.

## OFFLINE

The Edge dataset now includes entitlement quantities, consumable flags, entitlement types, and service points. Local evaluation supports offline decisions while Cloud remains authoritative.

## DOUBLE_SPEND

Offline double-spend is detected during reconciliation. BITORA keeps both facts, accepts the first valid Cloud consumption, rejects the later conflict, and records `ENTITLEMENT_DOUBLE_SPEND`.

## RECONCILIATION

V5.4 extends V5.2 reconciliation semantics with entitlement conflicts while preserving device auth, capability scope, idempotency, and append-only history.

## DEVICE_INTEGRATION

Devices require `CONSUME_ENTITLEMENT` capability. Devices without it are denied.

## PARTICIPANT_PORTAL

Foundation lookup exposes participant benefit state as available, consumed, exhausted, expired, revoked, or suspended without internal metadata.

## COMPANY_PORTAL

Company/delegation grants and scoped reporting are foundation-ready. Individual consumption visibility should remain policy-gated.

## ORGANIZER_VIEW

Organizer foundation supports creating types, service points, grants, revocations, adjustments, consumption reporting, and filters by entitlement type.

## AUDIT

Administrative operations are audited, including grants, revoke, suspend, and manual adjustments.

## DOMAIN_EVENTS

V5.4 records meaningful domain events: granted, revoked, consumed, exhausted, denied, and conflict detected.

## PRIVACY

Consumption history is treated as behavioral data. No public endpoints are exposed, and company-level visibility remains scoped.

## PERFORMANCE

Measured locally with SQLite temp DB. See `V5_4_PERFORMANCE_BASELINE.json`; numbers are reproducible baselines, not production capacity claims.

## BACKUP_RESTORE

Backup and isolated restore include entitlement types, service points, consumptions, adjustments, grant batches, and relationships.

## MULTITENANT

Consumption is scoped by organization and event. Cross-event and cross-tenant attempts are rejected as unknown credentials.

## GOLDEN_DATASET

Golden Access Dataset remains V4 10/10 and V5 10/10 with zero divergences.

## TEST_RESULTS

Dedicated verifier: `verificar_v5_4_entitlements_vouchers.py`.

Result: PASS.

## NO_REGRESSION

Required V4/V5.0/V5.1/V5.2/V5.3/V5.4 gates and secret scan passed.

## RISKS

- No monetary/cashless flows are implemented.
- UI is foundation-level, not final visual design.
- Offline double-spend can be detected and reconciled, not magically prevented across disconnected devices.
- Performance is local SQLite only.
- Company consumption visibility needs product policy before a final UI.

## ROLLBACK

Set `entitlements_vouchers = OFF`. Existing grants, consumptions, adjustments, audit, and domain events remain stored; V4 through V5.3 continue operating.

## NEXT_RECOMMENDED_EXECPLAN

V5.5 — Lead Retrieval.
