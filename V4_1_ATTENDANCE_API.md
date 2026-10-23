# V4.1 Attendance API

## Endpoints

- `POST /api/events/{event_id}/attendance`
- `GET /api/events/{event_id}/attendance`
- `GET /api/events/{event_id}/attendance/{attendance_id}`
- `GET /api/events/{event_id}/attendance/{attendance_id}/events`
- `POST /api/events/{event_id}/attendance/{attendance_id}/correct`
- `POST /api/events/{event_id}/attendance/{attendance_id}/invalidate`
- `GET /api/events/{event_id}/participants/{participant_id}/attendance`

## Escrituras

Requieren `attendance_v4_enabled`, autenticacion si corresponde, permiso backend e idempotency key.

## Filtros

`participant_id`, `activity_id`, `status`, `source`, `from`, `to`, `limit`, `offset`.

## Errores

Incluye `ATTENDANCE_FEATURE_DISABLED`, `ATTENDANCE_IDEMPOTENCY_CONFLICT`, `ATTENDANCE_ACTIVITY_EVENT_MISMATCH`, `ATTENDANCE_PARTICIPANT_EVENT_MISMATCH`, `ATTENDANCE_INVALID_SOURCE`, `ATTENDANCE_INVALID_TRANSITION` y `ATTENDANCE_NOT_FOUND`.
