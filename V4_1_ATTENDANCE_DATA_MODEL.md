# V4.1 Attendance Data Model

## Tablas

### feature_flags

Controla `attendance_v4_enabled` por plataforma, organizacion o evento.

### attendance_records

Registro consolidado con `organization_id`, `event_id`, `participant_id`, `accreditation_id`, `activity_id`, tipo, estado, fuente, timestamps, actor, idempotency key, hash de payload, correlation id, metadata sanitizada e invalidacion.

### attendance_events

Historial append-only de eventos de dominio: recorded, corrected, invalidated, entry, exit y replay.

### attendance_corrections

Historial explicito de correcciones con estado anterior, nuevo estado, metadata anterior/nueva, motivo, actor y fecha.

## Indices

Incluye indices por organizacion/evento, evento/participante, evento/actividad, participante/fecha, estado, created_at, eventos por attendance y correcciones.

## Unicidad

`UNIQUE(organization_id, idempotency_key)` evita duplicados dentro del tenant y permite reutilizar la misma key en otra organizacion.
