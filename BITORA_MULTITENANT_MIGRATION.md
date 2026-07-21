# Migracion Multi-Tenant

## SQLite

La migracion se aplica en `init_db()`:

- crea tablas si no existen;
- agrega `organization_id` a eventos;
- agrega `organization_id` e `integration_id` a jobs y comunicaciones;
- crea `BITORA Principal`;
- asigna eventos existentes;
- vincula usuarios existentes.

## PostgreSQL

La migracion versionada es:

`backend/migrations/014_multitenant_integrations.sql`

Incluye tablas, columnas, indices y bootstrap inicial.

## Rollback conceptual

No se recomienda eliminar columnas una vez aplicada. Para rollback operativo se debe restaurar backup previo.
