# BITORA Staging Live Setup

## Objetivo

Levantar staging real mediante BDF para ejecutar pruebas live multi-tenant.

## Archivo local

Crear:

`deployment/staging/.env.staging`

Partir de:

`deployment/staging/.env.staging.example`

No subir `.env.staging` a Git.

## Variables obligatorias

- `APP_ENV=staging`
- `QR_DB_ENGINE=postgres`
- `QR_POSTGRES_DSN=postgresql://.../bitora_staging`
- `DATABASE_URL=postgresql://.../bitora_staging`
- `BITORA_DISABLE_EMBEDDED_WORKER=1`
- `BDF_WORKER_LIVE=1`
- `BITORA_STORAGE_PATH=/bitora/storage`
- `BITORA_INTEGRATION_ENCRYPTION_KEY`
- `EMAIL_SAFE_MODE=true`
- `EMAIL_FORCE_RECIPIENT`
- `WHATSAPP_SAFE_MODE=true`
- `WHATSAPP_FORCE_RECIPIENT`
- `GOOGLE_OAUTH_REDIRECT_URI`
- `META_OAUTH_REDIRECT_URI`

## Comandos

```bash
python deployment/scripts/bdf.py check
python deployment/scripts/bdf.py build
python deployment/scripts/bdf.py up
python deployment/scripts/bdf.py health
python deployment/scripts/bdf.py migrate
python deployment/scripts/bdf.py smoke-test
```

Si falta una variable critica, BDF debe bloquear el inicio.
