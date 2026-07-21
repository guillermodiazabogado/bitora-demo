# BITORA Live Integrations Test Report

## Estado

Se agregaron pruebas live-aware. Cada una informa:

- `contract`: valida arquitectura sin proveedor real.
- `sandbox`: tiene variables pero no se habilito `BITORA_LIVE_INTEGRATIONS=true`.
- `live`: se habilito ejecucion live y existen credenciales reales.

## Pruebas

- Google OAuth multi-tenant.
- Email multi-tenant.
- WhatsApp multi-tenant.
- Webhooks tenant-aware.
- Backup multi-tenant.
- Restore multi-tenant.
- Disaster recovery de integraciones.

## Resultado local esperado sin credenciales

Las pruebas de contrato pasan, pero los gates live del release quedan omitidos.

## Resultado ejecutado

Se ejecutaron:

- `verificar_google_oauth_multitenant_live.py`: contract, omitted por variables Google faltantes.
- `verificar_email_multitenant_live.py`: contract, omitted por variables email/safe mode faltantes.
- `verificar_whatsapp_multitenant_live.py`: contract, omitted por variables WhatsApp faltantes.
- `verificar_webhooks_multitenant_live.py`: contract, omitted por secretos webhook faltantes.
- `verificar_backup_multitenant_live.py`: contract, omitted por staging/PostgreSQL/storage faltantes.
- `verificar_restore_multitenant_live.py`: contract, omitted por staging/PostgreSQL/storage faltantes.
- `verificar_integrations_disaster_recovery.py`: contract, omitted por staging/PostgreSQL/worker live faltantes.

BSTF release ejecuto 42 validaciones. Las pruebas funcionales pasaron; el release quedo rechazado por gates live obligatorios omitidos.
