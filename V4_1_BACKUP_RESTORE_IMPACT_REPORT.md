# V4.1 Backup Restore Impact Report

## Backup

El backup de evento ahora exporta:

- `attendance_records`
- `attendance_events`
- `attendance_corrections`

La vista previa suma `attendance_records` al conteo operativo de asistencia.

## Restore

El restore remapea:

- old participant_id -> new person id;
- old accreditation_id -> new accreditation id;
- old activity_id -> new activity id;
- old attendance_id -> new attendance record id.

## Efectos Externos

La restauracion de asistencia V4.1 no dispara jobs, comunicaciones, certificados ni encuestas.

## Validacion Ejecutada

- `verificar_event_restore.py`: PASSED.
- `verificar_v4_1_attendance_domain.py`: PASSED para presencia de `attendance_records` dentro del payload de backup de evento.

## Resultado

Attendance tables in backup: PASSED
Attendance restore mapping: PASSED
External effects: 0
