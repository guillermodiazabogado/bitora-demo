# BITORA Online Architecture

Fecha: 2026-08-04

## Objetivo

Definir la arquitectura online minima para publicar BITORA V4 sin usar una PC personal ni credenciales versionadas.

## Servicios requeridos

- Web app BITORA.
- PostgreSQL administrado o PostgreSQL dedicado.
- Worker separado.
- Storage persistente para archivos, exports, certificados y backups.
- Logs persistentes.
- HTTPS gestionado por el proveedor.
- Variables secretas externas al repositorio.

## Entornos

- Local/demo: puede usar SQLite.
- Staging: debe usar PostgreSQL, HTTPS, Safe Mode ON y Live Mode OFF.
- Produccion: debe usar PostgreSQL, HTTPS, secretos independientes y aprobacion humana expresa.

## Estado actual

Existe un servicio publico demo en Render que responde health, pero no cumple staging V4 porque reporta `env=demo` y no PostgreSQL obligatorio.

Estado: `READY FOR HOSTING CREDENTIALS`.
