# BITORA V5.0 Implementation Report

Fecha: 2026-09-25
Rama: deployment/v4-online
HEAD base inspeccionado: 73a76cb55102048cb05deba8543cfc0d9f73d690

## SUMMARY

V5.0 Enterprise Core Shadow Model fue implementado como fundacion aditiva. No reemplaza V4, no cambia QR, no cambia `/api/validate`, no altera tokens existentes y no introduce comportamiento visible para usuarios finales.

Estado de cierre: PARTIAL, porque el verificador V5.0 propio pasa, pero el gate legacy `verificar_v4.py` falla por una expectativa preexistente de texto en portal participante y el secret scan global falla por un archivo ajeno/untracked de Viviendas Roca.

## FILES CHANGED

- backend/migrations/036_v5_0_enterprise_core_shadow.sql
- backend/services/enterprise_core.py
- backend/database.py
- backend/services/backup.py
- server.py
- verificar_v5_0_enterprise_core_shadow.py
- docs/enterprise-evolution/V5_0_IMPLEMENTATION_REPORT.md

## DATABASE CHANGES

Migracion aditiva:

- enterprise_entities
- enterprise_identities
- enterprise_credentials
- enterprise_doors
- enterprise_devices
- enterprise_entitlements
- enterprise_rules
- enterprise_domain_events

Indices:

- scope indexes por organization/event/status.
- idempotency indexes parciales para claves no vacias.

No hubo DROP, rename destructivo ni cambios a tablas V4 existentes.

## DOMAIN MODEL IMPLEMENTED

Implementado:

- Entity shadow para PERSON, CREDENTIAL, COMPANY y base extensible para DEVICE/VEHICLE/STAND/DELEGATION.
- Identity separada de Entity.
- Credential shadow para QR/token actual mediante hash y token_hint, sin almacenar token plano.
- Entitlement base con allocated/consumed/consumable/status/validity.
- Rule base persistente sin motor complejo.
- Door foundation relacionada opcionalmente con event_zones V4.
- Device foundation sin secretos ni autenticacion de dispositivo todavia.
- Domain Event Log minimo append-only/idempotente.

## FEATURE FLAG

Flag nuevo:

- enterprise_core_model

Default:

- OFF

Con flag OFF:

- V4 no ejecuta shadow model automaticamente.

Con flag ON:

- el servicio puede ejecutar backfill/control shadow, sin decidir accesos ni alterar operaciones V4.

## SHADOW BEHAVIOR

El backfill crea mappings idempotentes desde V4:

- people -> enterprise_entities PERSON + enterprise_identities.
- accreditations -> enterprise_entities CREDENTIAL + enterprise_credentials.
- people.company -> enterprise_entities COMPANY por evento.

V4 sigue siendo autoridad. `/api/validate` sigue usando AccessValidationService existente.

## BACKFILL

Verificado:

- primera ejecucion crea mappings;
- segunda ejecucion no duplica;
- cross-tenant backfill se bloquea;
- conflictos/errores se reportan.

## BACKUP_RESTORE

Event backup incluye tablas V5.0.

Event restore remapea:

- event_id;
- people;
- accreditations;
- event_zones;
- enterprise_entities;
- enterprise_credentials;
- enterprise_entitlements;
- enterprise_devices.

Como restore de evento regenera tokens V4, las enterprise_credentials restauradas quedan `INACTIVE`, sin token hash/hint viejo, para evitar afirmar una credencial shadow inconsistente.

## TESTS EXECUTED

PASSED:

- verificar_v5_0_enterprise_core_shadow.py
- verificar_seguridad_basica.py
- verificar_multievent_isolation_20_events.py
- verificar_backup_restore.py
- verificar_v4_6_zone_permissions_foundation.py
- py_compile backend/services/enterprise_core.py verificar_v5_0_enterprise_core_shadow.py

FAILED / preexistente o fuera de alcance:

- verificar_v4.py: falla en "No abre portal participante" por expectativa de texto `Credencial digital`.
- verificar_participant_experience_v4_0_3.py: falla `portal_event_scope`.
- scripts/secret_scan.py: detecta token pattern en assets/logo-roca-2026-data-url.txt, archivo untracked ajeno a BITORA/V5.

## NO_REGRESSION_RESULTS

Resultado: PARTIAL.

Evidencia positiva:

- seguridad basica PASSED;
- multievent isolation PASSED;
- backup/restore productivo PASSED;
- zones V4.6 PASSED;
- test explicito de proteccion V5.0 confirma que V5 no cambia decisiones V4 para QR valido, token inexistente y acreditacion cancelada.

Bloqueo:

- gate legacy general no queda verde por fallos existentes no introducidos por V5.0.

## KNOWN_LIMITATIONS

- No hay API publica V5.0.
- No hay UI V5.0.
- No hay Access State Engine.
- No hay Device API completa.
- No hay Edge Sync.
- No hay drivers/hardware.
- No hay enforcement de entitlements.
- No hay consumo operacional de vouchers.
- Domain events no reemplazan audit_logs.

## RISKS

- Hay que resolver o actualizar gates legacy antes de declarar no-regression PASS completo.
- Secret scan global queda contaminado por archivos ajenos de QR Viviendas Roca.
- La endurance Railway/R2 sigue RUNNING y no puede usarse todavia como baseline final PASSED.

## ROLLBACK

Rollback operacional:

- mantener `enterprise_core_model = OFF`.

Con flag OFF:

- V4 continua usando sus rutas, QR, tokens y access validation actuales.

No borrar tablas V5 automaticamente; quedan como evidencia shadow/diagnostico.

## NEXT_RECOMMENDED_EXECPLAN

Antes de V5.1:

1. limpiar/separar archivos ajenos de Viviendas Roca para que secret scan global vuelva a ser util;
2. decidir si se actualizan verificadores legacy de portal a la UI actual;
3. esperar cierre/verificacion de endurance Railway/R2.

Luego avanzar a:

V5.1 - Access State Engine Shadow.
