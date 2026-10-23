# V4.1 Migration Report

## Migracion

`backend/migrations/016_v4_1_attendance_domain.sql`

## Tipo

Aditiva.

## Objetos

- `feature_flags`
- `attendance_records`
- `attendance_events`
- `attendance_corrections`
- indices operativos y multitenant.

## Datos Existentes

No se altera ni backfillea informacion existente.

## Idempotencia

Usa `CREATE TABLE IF NOT EXISTS` y `CREATE INDEX IF NOT EXISTS`.

## Validacion Ejecutada

- `deployment/scripts/bdf.py migrate`: PASSED.
- `deployment/scripts/bdf.py smoke-test`: PASSED.

## Rollback Tecnico

Como no hay backfill ni alteraciones destructivas, rollback de aplicacion es viable mientras no se hayan empezado a depender de datos V4.1. Para datos ya generados, conservar backup y aplicar restore si se requiere retiro total.
