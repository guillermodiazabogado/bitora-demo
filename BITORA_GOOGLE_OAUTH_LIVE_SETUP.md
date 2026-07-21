# Google OAuth Live Setup Multi-Tenant

Estado actual: preparado para validacion contract/sandbox. Flujo OAuth HTTP completo pendiente.

## Variables

- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `GOOGLE_OAUTH_REDIRECT_URI`

## Reglas

- El `state` debe incluir organizacion, usuario, evento opcional y nonce.
- El `state` debe ser de un solo uso.
- Tokens deben guardarse cifrados.
- La API nunca debe devolver access token ni refresh token.
- Una integracion Google de Alfa no puede asignarse a evento Beta.

## Prueba

```bash
python verificar_google_oauth_multitenant_live.py
```

La prueba reporta `contract`, `sandbox` o `live`.
