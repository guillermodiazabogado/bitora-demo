# BITORA Environment Configuration

Fecha: 2026-08-04

## Reglas

No versionar archivos `.env`.

Los secretos deben cargarse desde el panel del proveedor o un secret manager.

## Variables criticas

- `APP_ENV` o `BITORA_ENV`.
- `PORT`.
- `SECRET_KEY`.
- `SESSION_SECRET`.
- `QR_DB_ENGINE`.
- `QR_POSTGRES_DSN`.
- `DATABASE_URL`.
- `BITORA_PUBLIC_URL` o `BASE_URL`.
- `BITORA_SAFE_MODE`.
- `BITORA_LIVE_MODE`.
- `BITORA_COOKIE_SECURE`.
- `BITORA_ALLOWED_HOSTS`.
- `BITORA_CORS_ORIGINS`.
- `BITORA_STORAGE_PATH`.
- `BITORA_INTEGRATION_ENCRYPTION_KEY`.
- `EMAIL_*`.
- `GOOGLE_OAUTH_*`.
- `WHATSAPP_*`.

## Staging requerido

- `QR_DB_ENGINE=postgres`.
- `BITORA_SAFE_MODE=true`.
- `BITORA_LIVE_MODE=false`.
- HTTPS obligatorio.
- Credenciales demo bloqueadas.

## Produccion requerida

- PostgreSQL independiente.
- Secretos independientes.
- Safe Mode ON al inicio.
- Live Mode OFF hasta autorizacion expresa.
