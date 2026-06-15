# Estado de migracion backend

Objetivo: estabilizar arquitectura sin cambiar endpoints ni agregar funciones visibles.

## Migrado a servicios

### QRService

Archivo: `backend/services/qr.py`

- Normaliza payload de token.
- Verifica existencia de acreditacion antes de generar QR.
- El algoritmo grafico `qr_svg` sigue temporalmente en `server.py`.

### AccessValidationService

Archivo: `backend/services/access_validation.py`

- Regla autoritativa de validacion QR.
- Controla QR inexistente, acreditacion cancelada, tipo no habilitado, QR ya usado, reingresos y acceso a actividad con reserva obligatoria.
- Registra acceso y auditoria dentro de la transaccion del endpoint.

### ReservationService

Archivo: `backend/services/reservations.py`

- Crea reservas.
- Aplica lista de espera.
- Respeta solapamiento usando la regla existente.
- Promueve la siguiente reserva en espera.
- Consulta disponibilidad de cupos por servicio.

### CapacityBucketService

Archivo: `backend/services/capacity_buckets.py`

- Crea bolsas base por actividad.
- Calcula disponibilidad publica.
- Elige bolsa de cupo para fuente publica o recepcion.
- Mantiene la semantica previa de bolsas visibles/publicas.

### AuditService

Archivo: `backend/services/audit.py`

- Centraliza escritura de auditoria.
- Usa repositorio para aislar SQL.

### BackupService

Archivo: `backend/services/backup.py`

- Crea backups.
- Ejecuta checkpoint WAL antes de copiar.
- Aplica retencion.

### NotificationService

Archivo: `backend/services/notifications.py`

- Mantiene fachada de notificaciones por cola local.
- Email y WhatsApp siguen en modo preparado/demo.

## Capa de repositorio creada

Archivos:

- `backend/repositories/__init__.py`
- `backend/repositories/sqlite.py`
- `backend/repositories/events.py`
- `backend/repositories/participants.py`
- `backend/repositories/accreditations.py`
- `backend/repositories/activities.py`
- `backend/repositories/reservations.py`
- `backend/repositories/access.py`
- `backend/repositories/audit.py`
- `backend/repositories/capacity_buckets.py`
- `backend/repositories/communications.py`
- `backend/repositories/backups.py`

Responsabilidad:

- Aislar SQL usado por servicios.
- Preparar reemplazo futuro por `PostgresRepository`.
- Nombrar fronteras por dominio aunque hoy deleguen en SQLite.

## Compatibilidad mantenida

`server.py` conserva funciones historicas como fachada:

- `ensure_capacity_bags`
- `bag_usage`
- `public_availability`
- `pick_bag`
- `create_reservation`
- `activity_has_capacity`
- `promote_next_waitlisted`
- `audit`
- `create_db_backup`
- `prune_backups`

Los endpoints existentes siguen llamando las mismas rutas. `backend/app.py` sigue siendo la entrada principal.

## Reglas de negocio que todavia viven en server.py

- Inicializacion y migracion de esquema SQLite.
- Seed/demo inicial.
- Creacion/preparacion de evento real.
- ABM de eventos, tipos, usuarios, espacios y actividades.
- Validacion de horarios y solapamientos de actividades.
- Registro de acreditaciones y cupos por tipo.
- Preferencias de comunicacion y payload del portal.
- Centro de comunicaciones demo.
- Pantalla publica y configuracion.
- Alertas, summary, readiness y system-status.
- Exportaciones CSV/JSON.
- Auth por PIN y sesiones.
- Algoritmo completo de generacion QR SVG.
- HTTP routing y serializacion de respuestas.

## Pendiente recomendado

1. Extraer `EventService`, `AccreditationService`, `ActivityService` y `CommunicationService`.
2. Mover esquema/migraciones a `backend/database.py` o `backend/migrations`.
3. Separar repositorios por dominio: eventos, acreditaciones, actividades, reservas, accesos, comunicaciones.
4. Crear `PostgresRepository` con la misma interfaz.
5. Sacar reportes/exportaciones a `ReportService`.
6. Convertir `server.py` en capa HTTP delgada.
7. Mantener pruebas actuales como contrato de compatibilidad antes de cada migracion.

## Pruebas ejecutadas

- `verificar_mvp.py`
- `verificar_v2.py`
- `verificar_v3.py`
- `robustness_suite.py`
- `station_stress_test.py`
