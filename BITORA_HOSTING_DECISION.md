# BITORA Hosting Decision

Fecha: 2026-08-04

## Decision

No se crea infraestructura paga ni produccion en este sprint.

Estado: `READY FOR HOSTING CREDENTIALS`.

## Proveedor candidato

Render ya existe como entorno demo (`bitora-demo.onrender.com`), pero el servicio actual no es staging V4 certificado porque usa `env=demo`.

## Requisitos para elegir proveedor

- HTTPS automatico.
- PostgreSQL real.
- Variables secretas.
- Logs.
- Deploy desde GitHub.
- Health checks.
- Backups.
- Rollback.

## Accion manual pendiente

Confirmar si se reutiliza Render para crear `bitora-staging` con PostgreSQL o si se usa otro proveedor.
