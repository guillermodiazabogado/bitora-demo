# BITORA - Despliegue productivo

## Variables obligatorias

```env
APP_ENV=production
BASE_URL=https://app.bitora.ar
HTTPS_REQUIRED=true
QR_REQUIRE_LOGIN=1
QR_DB_ENGINE=postgres
QR_POSTGRES_DSN=postgresql://usuario:password@host:5432/bitora
QR_POSTGRES_POOL_MIN=2
QR_POSTGRES_POOL_MAX=10
STORAGE_BACKEND=local
BITORA_STORAGE_PATH=/var/lib/bitora/storage
QR_AUTO_BACKUP_MINUTES=60
QR_BACKUP_KEEP_LAST=30
```

En Render/Railway, `BITORA_STORAGE_PATH` debe estar sobre un disco persistente. Para S3 futuro usar `STORAGE_BACKEND=s3` cuando el adaptador externo sea habilitado.

## Deploy

1. Crear backup previo y verificarlo.
2. Publicar el commit aprobado.
3. Instalar `requirements.txt`.
4. Iniciar con `python backend/app.py`.
5. Las migraciones PostgreSQL se ejecutan al iniciar.
6. Confirmar `/health`, Diagnostico Tecnico y logs.
7. Probar login, inscripcion, QR, portal y backup.

## Rollback

1. Detener nuevas escrituras.
2. Volver al deploy anterior.
3. No revertir migraciones destructivamente.
4. Si el esquema o los datos quedaron incompatibles, restaurar el backup previo.
5. Ejecutar la suite de integridad antes de abrir.

## Logs y monitoreo

Monitorear API, PostgreSQL, jobs, backups, webhooks, storage, uptime, latencia media, p95 y errores recientes. Los logs nunca deben contener DSN, API keys o tokens.

## Recomendacion

Para eventos reales usar instancia paga con al menos 1 GB de RAM, PostgreSQL administrado, disco persistente y snapshots externos. Render Free queda limitado a demostraciones.
