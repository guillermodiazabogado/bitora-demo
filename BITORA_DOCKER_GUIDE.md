# BITORA Docker Guide

Fecha: 2026-08-04

## Staging local

BITORA se levanta mediante:

```powershell
docker compose -f deployment\docker-compose.staging.yml up -d
```

Servicios:

- `bitora-staging-app`.
- `bitora-staging-postgres`.
- `bitora-staging-worker`.
- `bitora-staging-monitor`.

## Reglas

- No incluir `.env` en la imagen.
- No incluir backups ni dumps.
- No incluir tokens.
- PostgreSQL debe ser servicio separado.
- Worker debe correr separado de la app.

## Validacion

```powershell
docker compose -f deployment\docker-compose.staging.yml ps
```

Health local:

```text
http://localhost:8788/health
```
