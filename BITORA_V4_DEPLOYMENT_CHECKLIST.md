# BITORA_V4_DEPLOYMENT_CHECKLIST

## Pre-deploy

- Working tree limpio.
- Rama esperada.
- Secret scan sin hallazgos.
- `.env.staging` no versionado.
- Docker operativo.
- PostgreSQL healthy.
- Storage healthy.
- Worker up.
- Safe Mode activo.

## Validacion

- V4.1 a V4.10: PASSED.
- Seguridad: PASSED.
- Convivencia: PASSED.
- Multievent isolation: PASSED.
- Backup/restore: PASSED.
- BDF health/migrate/smoke-test: PASSED.
- BSTF release: debe quedar aprobado antes de tag estable.

## Bloqueo actual

No desplegar como release estable hasta corregir gates live WhatsApp/Webhooks.
