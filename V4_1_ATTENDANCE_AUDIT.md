# V4.1 Attendance Audit

## Acciones

- `attendance.created`
- `attendance.corrected`
- `attendance.invalidated`
- `attendance.idempotency_replayed`
- `attendance.permission_denied`

## Payload

Incluye actor, organization_id, event_id, participant_id, activity_id, attendance_id cuando aplica, correlation_id, estado, fuente y motivo.

## Exclusiones

No registra secretos, tokens, credenciales, headers ni payloads completos de proveedores.
