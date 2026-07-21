# BITORA Staging Execution Report

## Objetivo

Ejecutar staging real mediante BDF y obtener certificacion Release completa sin gates `OMITTED`.

## Commit base

`6e05890e1c743911021a26426d7a5881e8355745`

## Infraestructura verificada

Fecha de ejecucion: 2026-07-20

Resultado:

- Docker: no disponible en PATH.
- Docker Compose: no disponible.
- WSL: no instalado.
- `winget`: no disponible.
- `deployment/docker-compose.staging.yml`: existe.
- `deployment/staging/.env.staging.example`: existe.
- `deployment/staging/.env.staging`: creado localmente y no versionado.
- Safe Mode: configurado en `.env.staging`.
- PostgreSQL: preparado en Docker Compose, no ejecutado por falta de Docker.
- Worker separado: preparado en Docker Compose, no ejecutado por falta de Docker.
- Storage persistente: preparado en Docker Compose, no ejecutado por falta de Docker.
- Monitor: preparado en Docker Compose, no ejecutado por falta de Docker.

## Variables configuradas sin secretos

En `deployment/staging/.env.staging` local:

- `APP_ENV=staging`
- `QR_DB_ENGINE=postgres`
- `QR_POSTGRES_DSN=postgresql://.../bitora_staging`
- `DATABASE_URL=postgresql://.../bitora_staging`
- `BITORA_DISABLE_EMBEDDED_WORKER=1`
- `BDF_WORKER_LIVE=1`
- `BDF_STAGING_LIVE=1`
- `BITORA_STORAGE_PATH=/bitora/storage`
- `BITORA_BACKUP_PATH=/bitora/backups`
- `BITORA_INTEGRATION_ENCRYPTION_KEY` configurada localmente.
- `EMAIL_SAFE_MODE=true`
- `EMAIL_FORCE_RECIPIENT` configurado con destinatario de staging.
- `WHATSAPP_SAFE_MODE=true`
- `WHATSAPP_FORCE_RECIPIENT` configurado con numero de prueba.
- `GOOGLE_OAUTH_REDIRECT_URI` configurado.
- `META_OAUTH_REDIRECT_URI` configurado.

No se cargaron credenciales productivas ni de clientes.

## Comandos ejecutados

```bash
python deployment/scripts/bdf.py check
```

Resultado:

- Python OK.
- Compose file OK.
- Env example OK.
- Env file OK.
- Safe env OK.
- Docker no disponible.
- Docker Compose no disponible.

```bash
python deployment/scripts/bdf.py build
python deployment/scripts/bdf.py up
python deployment/scripts/bdf.py status
```

Resultado:

`BDF ERROR: Docker no esta instalado o no esta disponible en PATH.`

```bash
python deployment/scripts/bdf.py health
```

Resultado:

- APP: UNHEALTHY.
- POSTGRES: UNKNOWN.
- STORAGE: UNHEALTHY.
- SAFE_MODE: ACTIVE.
- BACKUP: AVAILABLE.

## Hallazgos

### Bloqueante

Docker no esta instalado/disponible. Por lo tanto no se puede levantar staging real ni ejecutar PostgreSQL, worker, monitor, backup ni restore live.

### Correccion aplicada

BDF ahora detecta la ausencia de Docker y devuelve error claro, sin traceback.

## Proveedores

No se configuraron proveedores sandbox/live reales:

- Google OAuth: pendiente.
- Email staging real: pendiente.
- Meta/WhatsApp sandbox: pendiente.

## Resultado

Staging live no pudo ejecutarse en esta maquina por falta de Docker/Compose.
