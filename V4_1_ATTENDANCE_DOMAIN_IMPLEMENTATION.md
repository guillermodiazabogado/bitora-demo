# V4.1 Attendance Domain Implementation

## Archivos Principales

- `backend/services/attendance.py`
- `backend/migrations/016_v4_1_attendance_domain.sql`
- `server.py`
- `backend/services/backup.py`
- `verificar_v4_1_attendance_domain.py`

## Operaciones

- `record_attendance`
- `record_entry_v4`
- `record_exit_v4`
- `correct_attendance`
- `invalidate_attendance`
- `get_attendance`
- `list_attendance`
- `get_participant_attendance_history`
- `list_attendance_events`

## Principios Implementados

Validacion de tenant, validacion de actividad/evento, participante vinculado por acreditacion, metadata permitida, idempotencia, auditoria y transacciones desde los endpoints.

## No Implementado En Este Sprint

No hay cierre, certificados, encuestas, porcentajes academicos ni jobs nuevos.
