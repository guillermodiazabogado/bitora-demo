# BITORA Staging Live Report

Estado actual: preparado para ejecucion BDF, no levantado en este entorno.

## Validaciones BDF endurecidas

BDF ahora bloquea staging si falta:

- `APP_ENV=staging`;
- DSN apuntando a `bitora_staging`;
- `BITORA_INTEGRATION_ENCRYPTION_KEY`;
- `BITORA_DISABLE_EMBEDDED_WORKER=1`;
- `BDF_WORKER_LIVE=1`;
- `BITORA_STORAGE_PATH`;
- safe mode email/WhatsApp;
- destinatarios forzados;
- callbacks Google/Meta no productivos.

## Pendiente real

Ejecutar con Docker activo y `deployment/staging/.env.staging` local completo.

## Evidencia ejecutada

`python deployment/scripts/bdf.py check`

Resultado:

- compose file: OK;
- env example: OK;
- `.env.staging`: faltante;
- Docker: no disponible;
- Docker Compose: no disponible;
- safe env: no validable por falta de `.env.staging`.
