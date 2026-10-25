# BITORA V5 Discovery - Target Architecture

## Principio

Evolucion incremental sobre V4. No reescritura. La arquitectura propuesta agrega capas de dominio y contratos sin romper endpoints, tokens ni backups existentes.

## Capas Propuestas

1. Core Legacy Compatibility
   - Mantiene events, people, accreditations, activities, reservations y endpoints actuales.

2. Enterprise Domain Layer
   - Entity;
   - Identity;
   - Credential;
   - Entitlement;
   - Rule;
   - Zone;
   - Door;
   - Device;
   - Company/Delegation.

3. Access State Engine
   - Valida QR/credential existente.
   - Evalua reglas, ventanas, zonas, anti-passback, cooldown.
   - Escribe eventos de acceso append-only.

4. Sync/Edge Layer
   - Dataset minimo por evento/dispositivo.
   - Cola persistente local.
   - Reconciliacion deterministica server-authoritative.

5. Device API
   - Contratos para scanner, printer, kiosk, NFC/RFID, turnstile, camera.
   - Adapters externos sin contaminar core.

6. Operations Telemetry
   - Command Center consume access events, jobs, devices, R2, DB, queues y analytics.

## Modelo De Integracion Con V4

- accreditations sigue siendo fuente para credencial QR actual.
- Entity se puede crear como extension: PERSON apunta a people/accreditations.
- Entitlement referencia event_id, entity_id, scope, quantity/state.
- Rule evalua condiciones sin cambiar inicialmente /api/validate.
- Access State Engine puede correr detras de feature flag y comparar decisiones contra motor actual.

## Feature Flags Recomendados

- enterprise_core_model;
- access_state_engine_shadow;
- access_state_engine_enforced;
- edge_sync;
- device_api;
- delegations;
- entitlements;
- lead_retrieval;
- vapp;
- command_center_v5.

## No Breaking Changes

No romper:

- /api/portal?token=;
- /api/qr.svg?token=;
- /api/validate;
- accreditations.token;
- backup ZIP schema existente;
- exports CSV/JSON existentes;
- event_id/person_id/accreditation_id.

## Breaking Change Proposals

Ninguno aprobado en discovery. Cualquier cambio futuro a identidad/token debe entrar como compatibilidad paralela y migracion reversible.
