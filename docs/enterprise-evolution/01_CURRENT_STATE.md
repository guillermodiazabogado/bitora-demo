# BITORA V5 Discovery - Current State

Fecha: 2026-09-25
Rama inspeccionada: deployment/v4-online
HEAD inspeccionado: 73a76cb55102048cb05deba8543cfc0d9f73d690

## Git Safety

Working tree no esta limpio antes de esta fase por cambios ajenos no relacionados:

- R2_RESTORE_ISOLATED_VALIDATION.json modificado.
- .codex-remote-attachments/ sin versionar.
- QR-SORTEO-PARTICIPAR.png sin versionar.
- assets/, google-apps-script/, salidas/, visualizations/ sin versionar.
- generar_grafica_qr_roca.py sin versionar.

Esta discovery solo agrega documentacion bajo docs/enterprise-evolution/.

## Arquitectura Real

BITORA es una aplicacion web Python con frontend estatico y backend monolitico modularizado parcialmente.

Componentes encontrados:

- Entrada HTTP principal: backend/app.py y server.py como compatibilidad historica.
- Frontend: static/ y frontend/ con panel operativo, portal participante, recepcion, acceso, comunicaciones, encuestas, operaciones, networking y paginas auxiliares.
- Servicios de dominio: backend/services/.
- Repositorios: backend/repositories/.
- Persistencia: PostgreSQL en entorno online y SQLite para modo local/demo.
- Migraciones: backend/migrations/001 a 035, con migraciones aditivas por dominios V4.
- Storage: backend/storage.py con backend local/R2.
- Backups/restore: backend/services/backup.py.
- Jobs: backend/jobs.py y backend/services/jobs.py.
- Verificadores: verificar_*.py, tools/supertest/ y tools/endurance_*.

## Runtime Online Observado

Entorno de pruebas actual:

- URL Railway: https://web-production-7f9ac.up.railway.app
- Health/ready fueron validados previamente como operativos con PostgreSQL y R2.
- Hay una endurance Railway/R2 actualmente en ejecucion: ENDURANCE-RAILWAY-R2-24H-20260924-213816. No se declara PASSED hasta que finalice y sea verificada.

## Core

| Modulo | Estado | Evidencia |
| --- | --- | --- |
| eventos | EXISTS | events, backend/API_CONTRACT.md, frontend/index.html |
| participantes/personas | EXISTS | people, accreditations, repositories/participants.py |
| inscripciones | EXISTS | POST /api/register, accreditations |
| credenciales | EXISTS | print.html, QRService, certificates |
| QR/tokens | EXISTS | /api/qr.svg, QRService, accreditations.token |
| recepcion/check-in | EXISTS | accreditations status, access_logs |
| validacion de acceso | EXISTS | AccessValidationService, /api/validate |
| actividades/reservas | EXISTS | activities, reservations, capacity_bags |
| listas de espera | EXISTS | reservations/capacity services |
| roles/permisos | EXISTS | users, user_event_roles, role_permissions |
| auditoria | EXISTS | audit_logs, AuditService |

## Experience

| Modulo | Estado | Evidencia |
| --- | --- | --- |
| portal participante | EXISTS | static/p.html, /api/portal |
| agenda/actividades | EXISTS | activities, reservations |
| asistencia | EXISTS | activity_attendance, AttendanceService |
| certificados | EXISTS | CertificateService, certificate_* tables |
| encuestas | EXISTS | SurveyService, survey_* tables |
| networking | EXISTS | NetworkingService, networking pages |
| comunicaciones | PARTIAL | legacy queue + V4 communications automation; email live blocked by provider/domain config |
| credencial digital | EXISTS | portal + QR/print |

## Operations

| Modulo | Estado | Evidencia |
| --- | --- | --- |
| pantalla publica | EXISTS | public_display_* tables |
| dashboards | EXISTS | /api/summary, analytics_v4 |
| Operations Center | PARTIAL | operations_center_* tables/service, UI requiere hardening |
| exportaciones | EXISTS | CSV/JSON/export jobs |
| terminales/dispositivos | PARTIAL | device_type y NOC, sin Device API formal |
| occupancy | PARTIAL | metricas por reservas/visual; no sensor/camara formal |

## Infrastructure

| Componente | Estado | Evidencia |
| --- | --- | --- |
| base de datos | EXISTS | PostgreSQL/SQLite abstraction |
| storage | EXISTS | local/R2 |
| queues/jobs | PARTIAL | local jobs + communication queues; no broker durable externo |
| cache | PARTIAL | TTLCache, frontend localStorage parcial |
| websockets/SSE | NOT FOUND | no contrato real observado |
| autenticacion | EXISTS | /api/auth/login, users.pin_hash |
| autorizacion/RBAC | EXISTS | role permissions, user event roles |
| backup/restore | EXISTS | BackupService/EventRestoreService |
| observabilidad | PARTIAL | diagnostics, health/ready, endurance artifacts |
| deployment | EXISTS | Dockerfile, render.yaml, Railway online |
