# BITORA Online Backup Restore Report

Fecha: 2026-08-04

Rama: `deployment/v4-online`

HEAD: `4c70d4224acba79f3fc140ae1413248d165f4f59`

## Estado

Backup/Restore multitenant live local/staging Docker: PASSED historico.

Backup/Restore online remoto en Render: BLOCKED.

## Evidencia remota

Remote `/health`:

- `env`: `staging`
- `db`: `online`
- `storage.backend`: `local`
- `storage.ready`: true
- `backup`: `missing`

Remote `/ready`:

- `status`: `ready`
- `storage`: true
- warning: `Storage local requiere disco persistente y backup externo`

Render dashboard:

- plan actual: `Free`
- discos persistentes: no soportados en plan Free
- upgrade requerido para Persistent Disks

## Resultado por componente

| Componente | Estado | Motivo |
| --- | --- | --- |
| PostgreSQL online | PASSED | Base Render creada y app conectada |
| Storage online | PARTIAL | Storage local listo, no persistente certificado |
| Backup online | BLOCKED | `backup=missing` |
| Restore online | NOT EXECUTED | No existe artefacto remoto persistente validado |
| Restore aislado | NOT EXECUTED | No debe ejecutarse sin backup online real |
| Restart persistence | NOT EXECUTED | Falta Persistent Disk o storage externo |

## Politica

No se considera aprobado el backup online hasta que exista un artefacto remoto real, con checksums, generado desde el staging Render y restaurado en un entorno aislado.

No se considera aprobado restore online hasta comparar datos, storage, integridad, secuencias, aislamiento y efectos externos igual a cero.

## Scripts disponibles

Se mantienen scripts reproducibles para PostgreSQL:

- `scripts/backup_postgres.ps1`
- `scripts/restore_postgres.ps1`

Controles:

- Restore requiere confirmacion `-Yes`.
- Restore queda bloqueado si `APP_ENV=production` o `BITORA_ENV=production`.
- Los scripts requieren `DATABASE_URL` y no imprimen secretos.

## Siguiente paso

Completar storage persistente online, revalidar `/health`, ejecutar backup remoto real y restore remoto aislado antes de mergear PR `#12`.
