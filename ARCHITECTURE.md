# Arquitectura objetivo

La plataforma queda organizada para crecer como frontend separado y backend central.

## Carpetas

```text
frontend/
  Aplicacion web: dashboard, recepcion, escaner QR, pantalla publica,
  portal participante y landing publica.

backend/
  API central, servicios de negocio, configuracion de base de datos,
  jobs/colas e integraciones externas.
```

`server.py` queda como compatibilidad de transicion. El nuevo punto de entrada es `backend/app.py`, que hoy reutiliza el servidor existente mientras la logica se migra por partes a servicios.

## Principios

- Toda regla critica vive en backend.
- El frontend consume API.
- No se duplica logica de negocio en frontend.
- QR se valida solamente contra backend.
- Cupos y reservas se calculan en backend.
- Auditoria se registra en backend.
- WhatsApp, email y pagos son servicios del backend.
- Las tareas externas pasan por una capa de jobs/colas.

## Servicios preparados

- `NotificationService`: fachada comun para notificaciones.
- `EmailService`: envio futuro de emails por cola.
- `WhatsAppService`: envio futuro de WhatsApp por cola.
- `PaymentService`: creacion futura de checkout y webhooks de pagos.
- `BackupService`: backups y retencion.
- `AuditService`: registro central de auditoria.
- `QRService`: generacion y payloads QR.
- `AccessValidationService`: frontera para validacion de accesos.
- `ReservationService`: reservas, espera y promociones.
- `CapacityBucketService`: bolsas de cupos y disponibilidad publica.

## V3 participante y comunicaciones

El portal personal pasa a ser el centro de experiencia del participante:

- Credencial y QR unico.
- Agenda personal.
- Reservas posteriores.
- Preferencias de comunicacion.
- Historial de comunicaciones.
- Novedades y espacio futuro para certificados.

El centro de comunicaciones queda en modo demo: no envia WhatsApp ni email reales, solo registra historial respetando consentimiento. La integracion productiva debe entrar por servicios del backend y jobs/colas.

## Base de datos

Produccion objetivo:

- PostgreSQL.

Modo local/demo:

- SQLite, usando `acreditaciones.sqlite3`.

La configuracion esta preparada en `backend/database.py`:

```text
QR_DB_ENGINE=sqlite | postgres
QR_SQLITE_PATH=acreditaciones.sqlite3
QR_POSTGRES_DSN=postgresql://...
```

La migracion real a PostgreSQL debe hacerse con una capa de repositorios/migraciones antes de usar produccion multiusuario en internet.

## Jobs/colas

`backend/jobs.py` deja una cola local minima para desacoplar llamadas externas. En produccion se puede reemplazar por Redis/RQ, Celery, Dramatiq, SQS u otra cola durable sin cambiar las llamadas de los servicios.

## Endpoints principales

El contrato visible queda documentado en `backend/API_CONTRACT.md`.

## Plan de migracion

1. Mantener la app operativa con `backend/app.py`.
2. Migrar reglas de negocio de `server.py` a servicios, una por una.
3. Agregar repositorios de datos para aislar SQLite/PostgreSQL.
4. Introducir migraciones de esquema versionadas.
5. Cambiar integraciones externas para que entren por servicios y jobs.
6. Separar despliegue frontend/backend cuando el API ya no dependa del servidor monolitico.

## Estado actual de migracion

Ver `backend/MIGRATION_STATUS.md`.

Reportes V4:

- `V4_MIGRATION_REPORT.md`
- `V4_TEST_REPORT.md`

## Reemplazo futuro de cola local

`backend/jobs.py` usa una cola local en memoria para modo demo/local. Para produccion puede reemplazarse por una cola durable manteniendo la misma intencion de API:

- Redis/RQ para trabajos simples.
- Celery para workflows con reintentos y workers multiples.
- Dramatiq para una capa liviana de jobs Python.
- SQS u otra cola administrada para despliegue cloud.

Las integraciones externas deben entrar por servicios del backend y publicar jobs, no ejecutarse directamente desde el frontend.
