# V4 Migration Report

## Diagnostico inicial

`server.py` sigue siendo la capa HTTP y de compatibilidad. La V4 no cambia endpoints ni flujo operativo, pero consolida servicios y repositorios para que la siguiente migracion sea mas segura.

## Logica que todavia vive en server.py

- Inicializacion de esquema SQLite y migraciones livianas.
- Seed/demo inicial.
- Creacion y preparacion de evento real.
- ABM de eventos, tipos, usuarios, espacios y actividades.
- Validacion de horarios de actividades.
- Registro de acreditaciones y cupos por tipo.
- Preferencias del portal participante.
- Comunicaciones demo.
- Pantalla publica y configuracion.
- Dashboard, alertas, readiness y system-status.
- Exportaciones CSV/JSON.
- Auth por PIN y sesiones.
- Algoritmo QR SVG completo.
- Routing HTTP y serializacion.

## Logica ya migrada a servicios

- `QRService`: payload y control de existencia de token.
- `AccessValidationService`: validacion QR, acceso, doble lectura, reserva obligatoria, logs y auditoria.
- `ReservationService`: reservas, espera, solapamiento y promocion.
- `CapacityBucketService`: bolsas, disponibilidad y seleccion de cupo.
- `AuditService`: escritura de auditoria.
- `BackupService`: backup, retencion e integridad.
- `NotificationService`, `EmailService`, `WhatsAppService`: colas demo/preparadas.
- `PaymentService`: fachada futura.

## Endpoints que dependen directamente de logica interna

- Eventos y preparacion: `/api/events`, `/api/prepare-event`.
- Tipos, usuarios, espacios y actividades.
- Portal participante y comunicaciones demo.
- Pantalla publica.
- Dashboard, alerts, summary, readiness, system-status.
- Exportaciones CSV/JSON.

## Migrado sin riesgo en V4

- Repositorios por dominio como frontera SQLite/PostgreSQL.
- Auditoria de acceso con `event_id`.
- Auditoria de backup con `event_id`.
- Verificacion de integridad de backup.
- Enlace de backup del frontend con `event_id`.
- Prueba final `verificar_v4.py`.

## Compatibilidad temporal

`server.py` mantiene funciones historicas como fachada para no romper scripts ni tests:

- `create_reservation`
- `promote_next_waitlisted`
- `public_availability`
- `pick_bag`
- `audit`
- `create_db_backup`
- `prune_backups`

## Repositorios preparados

- Eventos.
- Participantes.
- Acreditaciones.
- Actividades.
- Reservas.
- Accesos.
- Auditoria.
- Bolsas de cupos.
- Comunicaciones.
- Backups.

Hoy delegan o heredan `SQLiteRepository`; en V5 pueden tener implementacion PostgreSQL real.

## Seguridad operativa revisada

- Roles conservados.
- PINs iniciales conservados.
- Acceso no puede modificar cupos.
- Preparar evento real conserva backup previo.
- Backup manual ahora queda auditado.
- Estado del sistema informa integridad y edad de backup.
- Pantalla publica no expone DNI, email, telefono, operadores, auditoria ni datos internos de cupos.

## Pendiente para V5

1. Mover `EventService`, `AccreditationService`, `ActivityService` y `CommunicationService`.
2. Mover esquema a migraciones versionadas.
3. Crear `PostgresRepository` real.
4. Sacar reportes/exportaciones a `ReportService`.
5. Reducir `server.py` a capa HTTP delgada.
6. Agregar auth/token API si se separa frontend/backend en servidores distintos.
