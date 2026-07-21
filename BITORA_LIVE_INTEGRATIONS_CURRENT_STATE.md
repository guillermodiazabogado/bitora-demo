# BITORA Live Integrations - Estado Actual

Commit base auditado:

`3b5aca166b3da733e46011970413e1785a21d52f`

## Arquitectura existente

- Multi-tenant con `organizations`.
- Usuarios por organizacion en `organization_users`.
- Eventos con `events.organization_id`.
- Integraciones por organizacion en `organization_integrations`.
- Asignacion por evento/canal en `event_integrations`.
- Comunicaciones con `communication_queue.organization_id` e `integration_id`.
- Secretos cifrados con `BITORA_INTEGRATION_ENCRYPTION_KEY`.
- Safe mode global y por organizacion.
- BDF con Docker Compose para app, PostgreSQL, worker y monitor.
- BSTF con perfil release y gates live.

## Servicios existentes

- Email: `backend/services/email.py`.
- WhatsApp/Meta: `backend/services/whatsapp.py`.
- Jobs: `backend/services/jobs.py`.
- Backup/restauracion: `backend/services/backup.py`.
- Diagnostico: `backend/services/diagnostics.py`.
- Secretos de integraciones: `backend/services/integration_secrets.py`.

## Variables reales detectadas

- `APP_ENV`
- `BASE_URL`
- `QR_DB_ENGINE`
- `QR_POSTGRES_DSN`
- `DATABASE_URL`
- `BITORA_STORAGE_PATH`
- `BITORA_INTEGRATION_ENCRYPTION_KEY`
- `EMAIL_PROVIDER`
- `EMAIL_API_KEY`
- `EMAIL_FROM`
- `EMAIL_REPLY_TO`
- `EMAIL_SAFE_MODE`
- `EMAIL_FORCE_RECIPIENT`
- `EMAIL_WEBHOOK_SECRET`
- `WHATSAPP_PROVIDER`
- `WHATSAPP_ACCESS_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID`
- `WHATSAPP_BUSINESS_ACCOUNT_ID`
- `WHATSAPP_VERIFY_TOKEN`
- `WHATSAPP_APP_SECRET`
- `WHATSAPP_SAFE_MODE`
- `WHATSAPP_FORCE_RECIPIENT`
- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `GOOGLE_OAUTH_REDIRECT_URI`
- `META_OAUTH_REDIRECT_URI`

## Endpoints relevantes

- `GET /api/organizations`
- `POST /api/organizations`
- `GET /api/organization-integrations`
- `POST /api/organization-integrations`
- `POST /api/organization-integrations/test`
- `POST /api/organization-integrations/disable`
- `GET /api/event-integrations`
- `POST /api/event-integrations`
- `POST /api/communications/email/webhook`
- `POST /api/communications/whatsapp/webhook`

## Brechas detectadas

- Google OAuth no tiene flujo HTTP completo implementado.
- Webhooks resuelven mensajes por `provider_message_id`, pero la validacion tenant-aware live depende de proveedor real.
- BDF necesitaba endurecer validacion de clave de cifrado, worker separado y callbacks.
- BSTF necesitaba gates live con evidencia por prueba.
- Backup/restore multiorganizacion live requiere PostgreSQL y storage persistente activos.

## Riesgo principal

No se puede certificar live sin credenciales sandbox/staging reales y staging Docker activo.
