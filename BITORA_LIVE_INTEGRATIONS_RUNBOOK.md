# BITORA Live Integrations Runbook

## Orden operativo

1. Completar `deployment/staging/.env.staging`.
2. Ejecutar `python deployment/scripts/bdf.py check`.
3. Levantar staging con `python deployment/scripts/bdf.py up`.
4. Ejecutar migraciones.
5. Ejecutar smoke test.
6. Ejecutar pruebas live-aware.
7. Ejecutar `python deployment/scripts/bdf.py supertest --profile release`.
8. Revisar gates omitidos.
9. Completar credenciales faltantes.
10. Repetir hasta cero gates live obligatorios omitidos.

## Pruebas live-aware

- `verificar_google_oauth_multitenant_live.py`
- `verificar_email_multitenant_live.py`
- `verificar_whatsapp_multitenant_live.py`
- `verificar_webhooks_multitenant_live.py`
- `verificar_backup_multitenant_live.py`
- `verificar_restore_multitenant_live.py`
- `verificar_integrations_disaster_recovery.py`

## Regla

Un resultado `contract` o `sandbox` sirve como evidencia tecnica, pero no aprueba un gate live obligatorio.
