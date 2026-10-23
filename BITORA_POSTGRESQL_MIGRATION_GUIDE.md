# BITORA PostgreSQL Migration Guide

Estado: Render staging preparado, migracion remota pendiente.

## Politica

Staging y produccion deben iniciar exclusivamente con PostgreSQL. La aplicacion falla de forma segura si `APP_ENV=staging` o `APP_ENV=production` usa SQLite o no recibe `QR_POSTGRES_DSN`/`DATABASE_URL`.

## Variables requeridas

- `QR_DB_ENGINE=postgres`
- `QR_POSTGRES_DSN`
- `DATABASE_URL`

En Render, ambas URL se toman desde `bitora-staging-postgres` mediante `fromDatabase`.

## Validacion

1. Desplegar Blueprint.
2. Abrir `/health`.
3. Abrir `/ready`.
4. Confirmar que `database=true`.
5. Confirmar que `migrations=true`.
6. Confirmar que `env=staging`.

## Backup y restore

Scripts disponibles:

- `scripts/backup_postgres.ps1`
- `scripts/restore_postgres.ps1`

Ambos requieren `DATABASE_URL` y no imprimen secretos. Restore requiere `-Yes` y queda bloqueado en `APP_ENV=production`.
