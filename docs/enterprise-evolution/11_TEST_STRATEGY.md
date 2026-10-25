# BITORA V5 Discovery - Test Strategy

## Principio

V5 no puede degradar la baseline V4. Todo cambio debe demostrar compatibilidad funcional, datos coherentes y rollback.

## V5 No Regression Gate

Debe incluir:

- health/ready;
- seguridad basica;
- auth/RBAC;
- QR/access validation;
- participant portal;
- reservations/capacity;
- attendance;
- certificates;
- surveys;
- communications Safe Mode;
- analytics 70%/conteos coherentes donde aplique;
- backup/restore;
- multitenant/multievent;
- storage R2;
- jobs final 0/0;
- endurance aprobado cuando corresponda.

## Tests Existentes Relevantes

- verificar_v4.py;
- verificar_v4_1_attendance_domain.py;
- verificar_v4_2_attendance_closure_eligibility.py;
- verificar_v4_3_certificates_foundation.py;
- verificar_v4_4_surveys_foundation.py;
- verificar_v4_5_speakers_foundation.py;
- verificar_v4_6_zone_permissions_foundation.py;
- verificar_v4_7_history_autocomplete_foundation.py;
- verificar_v4_8_operations_center.py;
- verificar_v4_9_communications_automation.py;
- verificar_v4_10_analytics_functional_closure.py;
- verificar_backup_restore.py;
- verificar_multievent_isolation_20_events.py;
- tools/endurance_r2_24h_runner.py.

## Nuevos Tests Requeridos Para V5

- shadow decision: V4 access vs V5 access;
- entitlement grant/consume/idempotency;
- revocation;
- anti-passback;
- cooldown;
- current zone;
- device identity;
- offline queue replay;
- duplicate suppression;
- backup/restore V5 tables;
- rollback flag.

## Endurance

Endurance 24h no debe correrse en discovery. Para V5, usar la endurance V4 aprobada como baseline y crear endurance V5 solo despues de implementacion piloto.
