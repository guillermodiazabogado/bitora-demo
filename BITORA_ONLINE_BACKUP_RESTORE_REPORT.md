# BITORA Online Backup Restore Report

Fecha: 2026-08-04

## Estado

Backup/Restore multitenant live local/staging Docker: PASSED.

Backup/Restore online remoto: NOT EXECUTED.

## Requisito para online

Debe ejecutarse sobre PostgreSQL online y storage persistente online, con checksums y restore en entorno aislado.

## Politica

No se debe considerar aprobado el backup online hasta restaurar un artefacto real fuera del entorno principal.
# Render staging update - 2026-08-04

Estado: `READY FOR HOSTING CREDENTIALS`

Se agregaron scripts reproducibles para PostgreSQL:

- `scripts/backup_postgres.ps1`
- `scripts/restore_postgres.ps1`

La validacion remota de backup/restore en Render queda pendiente porque el servicio `bitora-staging` y la base `bitora-staging-postgres` aun no fueron creados.

Controles:

- Restore requiere confirmacion `-Yes`.
- Restore queda bloqueado si `APP_ENV=production` o `BITORA_ENV=production`.
- Los scripts requieren `DATABASE_URL` y no imprimen secretos.
