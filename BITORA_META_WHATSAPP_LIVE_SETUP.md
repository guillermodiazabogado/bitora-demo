# Meta WhatsApp Live Setup Multi-Tenant

## Variables

- `WHATSAPP_PROVIDER=meta`
- `WHATSAPP_ACCESS_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID`
- `WHATSAPP_BUSINESS_ACCOUNT_ID`
- `WHATSAPP_VERIFY_TOKEN`
- `WHATSAPP_APP_SECRET`
- `WHATSAPP_SAFE_MODE=true`
- `WHATSAPP_FORCE_RECIPIENT`
- `META_OAUTH_REDIRECT_URI`

## Prueba

```bash
python verificar_whatsapp_multitenant_live.py
```

Valida asignacion por organizacion/canal y deja pendiente live si no hay credenciales reales.
