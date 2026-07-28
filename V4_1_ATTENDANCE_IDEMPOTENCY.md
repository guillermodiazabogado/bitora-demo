# V4.1 Attendance Idempotency

## Regla

La idempotencia se controla por `organization_id + idempotency_key`.

## Escenarios

- Misma key y mismo payload: devuelve el resultado original y registra replay.
- Misma key y payload distinto: `ATTENDANCE_IDEMPOTENCY_CONFLICT`.
- Misma key en otra organizacion: permitido por scope tenant.
- Reintento concurrente: constraint evita duplicados.

## Hash

El hash se calcula sobre el payload normalizado sin datos sensibles.
