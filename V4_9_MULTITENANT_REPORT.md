# BITORA V4.9 Multitenant Report

Every V4.9 table stores `organization_id`.

Event-bound data also stores `event_id`.

The service validates event ownership before all read/write operations.

Verifier coverage:
- Cross-tenant segment preview attempt rejected.
- Messages, deliveries and provider events are resolved by organization and event.
- Recipients are derived only from accreditations in the requested event.

Cross-tenant accesses allowed: 0
