# BITORA Render Staging Readiness

Fecha: 2026-08-04

Rama: `deployment/v4-online`

Commit base: `5173691c24cc8d522bb51990f8a3ed96d09faa4a`

Estado: `READY FOR HOSTING CREDENTIALS`

## Resumen

BITORA quedo preparado para desplegar un staging online V4 en Render con Docker y PostgreSQL real. Render Dashboard esta autenticado y el Blueprint correcto fue abierto desde la rama `deployment/v4-online`, pero no se desplego porque Render requiere cargar los secretos de bootstrap antes de crear los recursos.

## Preparado

| Componente | Estado | Evidencia |
| --- | --- | --- |
| Rama de despliegue | PASSED | `deployment/v4-online` |
| Dockerfile | PASSED | Imagen local construida correctamente |
| Render Blueprint | PASSED | `render.yaml` define `bitora-staging` y `bitora-staging-postgres` |
| PostgreSQL obligatorio | PASSED | `APP_ENV=staging` rechaza SQLite |
| `/health` | PASSED | Validado en contenedor local con PostgreSQL |
| `/ready` | PASSED | Validado en contenedor local con PostgreSQL |
| Safe Mode | PASSED | `BITORA_SAFE_MODE=true` requerido |
| Live Mode | PASSED | `BITORA_LIVE_MODE=false` requerido |
| Bootstrap seguro | PASSED | Requiere usuario y password fuerte |
| Demo credentials online | PASSED | No se crean usuarios demo en staging/production |
| Secret scan | PASSED | `scripts/secret_scan.py` sin hallazgos reales |

## Pendiente externo

| Requisito | Estado |
| --- | --- |
| Autenticacion Render | PASSED |
| Creacion del Blueprint en Render | NOT EXECUTED |
| PostgreSQL Render creado | NO |
| Servicio web Render creado | NO |
| URL staging HTTPS | NOT AVAILABLE |
| Smoke remoto | NOT EXECUTED |
| Backup/restore remoto | NOT EXECUTED |

## Accion manual requerida

Completar en la pantalla abierta de Render los valores secretos marcados con `sync: false`:

- `BITORA_ADMIN_BOOTSTRAP_USER`
- `BITORA_ADMIN_BOOTSTRAP_PASSWORD`

Si Render solicita un plan pago para PostgreSQL o almacenamiento persistente, detener y confirmar aprobacion antes de crear recursos.
