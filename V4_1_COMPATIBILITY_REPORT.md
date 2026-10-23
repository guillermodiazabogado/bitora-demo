# V4.1 Compatibility Report

## Compatibilidad Mantenida

- No se modifican tablas existentes de forma destructiva.
- `activity_attendance` sigue funcionando.
- QR, acreditacion, reservas y certificados historicos no cambian su semantica.
- No se crean jobs nuevos.
- No se disparan comunicaciones.
- Endurance sigue diferido.

## Backup y Restore

El backup de evento incluye `attendance_records`, `attendance_events` y `attendance_corrections`. Restore remapea `participant_id`, `activity_id`, `accreditation_id` y `attendance_id`.

## Upgrade

La migracion `016_v4_1_attendance_domain.sql` es aditiva. No requiere backfill automatico.
