# V5.6 VAPP / Vehicle & Logistics Report

## SUMMARY

V5.6 implements the vehicle access and logistics foundation for BITORA. It supports vehicles, drivers, companies, access slots, gates, destinations, ENTRY/EXIT state, offline reconciliation, and logistics reporting behind `vehicle_logistics`.

## DOMAIN_MODEL

The model links Person, Vehicle, Company, Access Slot, Gate, and Destination while preserving Enterprise Entity separation.

## VEHICLES

`enterprise_vehicles` stores vehicles with deterministic plate normalization and optional make/model/color.

## DRIVERS

Drivers are linked by Enterprise Entity, avoiding copied personal data in vehicle records.

## COMPANY_INTEGRATION

Vehicles are scoped to Company/Event through explicit participation records.

## EVENT_PARTICIPATION

Vehicle existence does not imply authorization. `enterprise_vehicle_event_participation` controls event scope.

## ACCESS_SLOTS

`enterprise_vehicle_access_slots` defines temporal authorizations with gate, destination, purpose, validity, status, and entry limits.

## GATES

V5.6 reuses Enterprise Doors as vehicle gates.

## DESTINATIONS

`enterprise_logistics_destinations` models docks, stands, backstage, storage, parking, or service destinations, optionally linked to V5.5 Stand.

## TIME_WINDOWS

Slots validate `valid_from` and `valid_until` and deny outside-window attempts.

## VEHICLE_ACCESS_STATE

`enterprise_vehicle_state_snapshots` tracks OUTSIDE/INSIDE state independently from person access state.

## ACCESS_EVENTS

`enterprise_vehicle_access_events` stores append-only ENTRY/EXIT attempts with decision, reason, device, idempotency, and correlation.

## ANTI_PASSBACK

Vehicles already INSIDE are denied a second ENTRY unless a controlled manual override is used.

## ENTRY_LIMITS

Slots enforce configured entry limits and mark used slots.

## COMPANY_PORTAL

Foundation supports company-scoped vehicle registration, slot requests, and status checks.

## ORGANIZER_VIEW

Foundation supports review/approval, gate/window/destination assignment, overrides, inside vehicles, upcoming entries, and dashboards.

## BULK_IMPORT

CSV preview/validation foundation supports vehicle logistics imports with row-level errors.

## CAPACITY

Destination capacity is modeled; advanced optimization is intentionally out of scope.

## EDGE

Device capability `VALIDATE_VEHICLE` is required for vehicle validation at edge/gate terminals.

## OFFLINE

Offline ENTRY/EXIT can be queued and reconciled through the V5.2 Edge foundation.

## RECONCILIATION

Offline conflicts such as duplicate ENTRY are detected as `VEHICLE_ANTI_PASSBACK_CONFLICT`.

## ENTITLEMENT_INTEGRATION

V5.4 Parking entitlement compatibility is prepared but not required for every slot.

## STAND_INTEGRATION

Destinations can link to V5.5 Stands.

## OVERRIDES

Manual override is auditable and preserves the original decision metadata.

## SECURITY

Controls cover organization/event/company scope, driver validation, slot validation, device capability, idempotency, and audit/domain events.

## PRIVACY

Plate and driver data are scoped to organization, event, and company. No global plate search is exposed.

## PERFORMANCE

Measured locally with SQLite temp DB. See `V5_6_PERFORMANCE_BASELINE.json`.

## BACKUP_RESTORE

Backup/restore includes vehicles, event participation, destinations, slots, access events, state snapshots, and imports.

## MULTITENANT

Vehicle authorization does not cross tenants/events.

## GOLDEN_DATASET

Golden Access Dataset remains V4 10/10 and V5 10/10 with zero divergences.

## TEST_RESULTS

Dedicated verifier: `verificar_v5_6_vapp_vehicle_logistics.py`.

Result: PASS.

## NO_REGRESSION

Required V4 through V5.6 gates and secret scan passed.

## RISKS

- No LPR/camera/RFID/hardware adapter.
- No Command Center visual dashboard yet.
- No GIS/maps/routing optimization.
- Capacity is foundation-level.
- Performance is local SQLite only.

## ROLLBACK

Set `vehicle_logistics = OFF`. Existing vehicles, slots, events, states, overrides, audit, and domain events remain stored; V4 through V5.5 continue operating.

## NEXT_RECOMMENDED_EXECPLAN

V5.7 — Command Center.
