# BITORA Staging Deployment Guide

Fecha: 2026-08-04

## Estado

Staging local Docker: PASSED.

Staging publico V4: pendiente de credenciales/proveedor.

## Requisitos

- PostgreSQL online.
- HTTPS.
- Variables secretas externas.
- Safe Mode ON.
- Live Mode OFF.
- Worker separado.
- Storage persistente.
- Health y readiness accesibles.

## No usar

- SQLite para staging publico.
- Servicio demo como staging certificado.
- Credenciales en Git.
- Datos personales reales.

## Validacion remota requerida

- Health.
- Readiness.
- Login.
- Flujo principal.
- Multitenant.
- Multievent.
- Backup/Restore.
- Integraciones live controladas.
