# Email Live Setup Multi-Tenant

## Variables

- `EMAIL_PROVIDER`
- `EMAIL_API_KEY`
- `EMAIL_FROM`
- `EMAIL_REPLY_TO`
- `EMAIL_SAFE_MODE=true`
- `EMAIL_FORCE_RECIPIENT`
- `EMAIL_WEBHOOK_SECRET`

## Safe mode

En staging, todo envio debe redirigirse al destinatario forzado y marcarse como prueba.

## Prueba

```bash
python verificar_email_multitenant_live.py
```

Valida asociacion a organizacion, integracion, cola, safe mode y ausencia de cruces.
