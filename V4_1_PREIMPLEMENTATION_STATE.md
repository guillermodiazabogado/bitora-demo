# V4.1 Preimplementation State

Fecha: 2026-07-28
Rama inicial: develop/v4
Rama de trabajo: feature/v4.1-attendance-domain
Commit base: 48a439e33996d2922e7e7a9b541b1e51720d6269

## Estado Git

La rama partio exactamente del commit de arquitectura funcional V4. El working tree estaba limpio antes de implementar. La RC `bitora-v1.0.0-rc.1` no fue modificada.

## Servicios

Antes del sprint, BDF habia reportado app, PostgreSQL, storage y Safe Mode saludables, con worker y monitor activos. Este sprint no modifica infraestructura.

## Tests y Build Base

La compilacion Python de los archivos relevantes se ejecuta con el runtime empaquetado de Codex. El runner quick de BSTF tiene un hallazgo alto heredado en tooling de upgrade, documentado aparte.

## Migraciones

Migracion maxima previa: `015_role_permissions.sql`. V4.1 agrega una migracion aditiva `016_v4_1_attendance_domain.sql`.

## Hallazgos Conocidos

`deployment/scripts/certify_upgrade_from_previous_live.py` contiene un hallazgo alto preexistente de auditoria estatica. No se corrige en V4.1 por alcance.

## Alcance Autorizado

Dominio base de asistencia: registro, consulta, correccion, invalidacion, idempotencia, auditoria, RBAC, feature flag y compatibilidad con backup/restore.
