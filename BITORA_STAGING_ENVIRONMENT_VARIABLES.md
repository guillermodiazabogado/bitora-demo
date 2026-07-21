# BITORA Staging Environment Variables

Archivo ejemplo:

```text
deployment/staging/.env.staging.example
```

Archivo real ignorado por Git:

```text
deployment/staging/.env.staging
```

## Variables obligatorias

```text
APP_ENV=staging
BASE_URL=http://localhost:8788
QR_DB_ENGINE=postgres
QR_POSTGRES_DSN=postgresql://bitora_staging:...
DATABASE_URL=postgresql://bitora_staging:...
STORAGE_BACKEND=local
BITORA_STORAGE_PATH=/bitora/storage
BITORA_DISABLE_EMBEDDED_WORKER=1
BDF_WORKER_LIVE=1
EMAIL_SAFE_MODE=true
EMAIL_FORCE_RECIPIENT=...
WHATSAPP_SAFE_MODE=true
WHATSAPP_FORCE_RECIPIENT=...
```

## Reglas

- No usar `APP_ENV=production`.
- No usar base productiva.
- No usar storage productivo.
- No desactivar safe mode.
- No subir `.env.staging`.
