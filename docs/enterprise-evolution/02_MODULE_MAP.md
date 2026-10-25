# BITORA V5 Discovery - Module Map

## Dependencias Principales

| Modulo | Depende de | Escribe | Riesgo |
| --- | --- | --- | --- |
| eventos | organizations, users | events, event settings | Romper event_id afecta casi todo |
| personas/participantes | events, people | people, accreditations | people.email es unico global; cuidado multi-evento |
| QR/acceso | accreditations, accreditation_types, activities | access_logs, audit_logs, counters | Token existente no debe invalidarse |
| recepcion | accreditations, people, certificates | accreditations, people, cert state | Mezcla operaciones y emision |
| reservas | activities, capacity_bags, accreditations | reservations | Cupos y lista de espera deben ser transaccionales |
| asistencia | activities, reservations, accreditations | activity_attendance, certificate_eligibility | Base para certificados |
| certificados | attendance, eligibility, storage | certificate_* y assets R2/local | Persistencia de PDF es critica |
| encuestas | events, accreditations | survey_* | Privacidad/anonimato por umbral |
| comunicaciones | people, consent, accreditations, integrations | communication_queue, v4 messages | Proveedores externos y Safe Mode |
| operations center | diagnostics, jobs, incidents | operations_center_* | Falta tablero operacional maduro |
| analytics | tablas core + snapshots | analytics_v4_* | Riesgo de metricas inconsistentes |
| backup/restore | casi todas las tablas | ZIP/restore isolated | Compatibilidad de schema y tokens |

## Endpoints Criticos

- POST /api/auth/login
- GET /api/auth/me
- GET /api/events
- POST /api/events
- POST /api/register
- GET /api/portal?token=TOKEN
- GET /api/accreditations
- POST /api/accreditations/status
- POST /api/validate
- GET /api/qr.svg?token=TOKEN
- GET /api/summary
- GET /health
- GET /ready
- GET /api/backup
- POST /api/communications/send
- POST /api/communications/email/test

## Modulos Que Dependen De Participantes

- acreditaciones;
- QR;
- recepcion;
- acceso;
- reservas;
- asistencia;
- certificados;
- encuestas;
- comunicaciones;
- networking;
- analytics;
- backup/restore.

## Modulos Que Modifican Permisos

- User Management;
- matriz de permisos;
- role_permissions;
- user_event_roles;
- organization_users.

## Modulos Que Generan Auditoria

AuditService es usado por acceso, analytics, comunicaciones V4, backup/restore y otros servicios. La cobertura no es universal: algunas rutas legacy pueden escribir audit_logs directamente o no auditar cambios menores.

## Offline / Local

Existe localStorage para token networking y captation session, y modo SQLite/local. No se encontro motor offline formal para validacion de acceso, cola persistente local, sincronizacion incremental o reconciliacion cloud-edge-device.

## Single Points of Failure

- PostgreSQL online.
- Storage R2 para certificados/assets/backups.
- backend/app.py/server.py como nodo unico.
- Jobs locales si el proceso se reinicia.
- Provider email/WhatsApp externo para comunicaciones reales.
- Semantica actual de token de acreditacion.

## Acoplamientos Peligrosos

- server.py/backend app aun concentran rutas y reglas historicas.
- participants/accreditations/person email unico global limita delegaciones complejas.
- certificados dependen de asistencia/elegibilidad y storage.
- comunicaciones legacy y V4 conviven con modelos separados.
- operaciones/analytics leen muchas tablas sin un event log operacional unico.
