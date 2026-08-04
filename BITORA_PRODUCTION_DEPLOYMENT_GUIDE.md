# BITORA Production Deployment Guide

Fecha: 2026-08-04

## Estado

Produccion no desplegada.

## Condiciones previas

- Release/tag publicado.
- Staging publico HTTPS validado.
- PostgreSQL real.
- Backup/restore online probado.
- Safe Mode ON.
- Live Mode OFF.
- Secretos externos.
- Autorizacion humana expresa.

## Prohibido

- Usar SQLite.
- Usar credenciales demo.
- Activar comunicaciones reales sin aprobacion.
- Cargar datos reales sin autorizacion.
- Desplegar en PC personal.

## Primer arranque

Produccion debe iniciar con integraciones externas inactivas o en Safe Mode.
