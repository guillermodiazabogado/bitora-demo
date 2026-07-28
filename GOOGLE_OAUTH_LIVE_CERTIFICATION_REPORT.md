# BITORA Google OAuth Live Certification Report

Fecha: 2026-07-22

## Resultado final

```text
GOOGLE OAUTH LIVE CERTIFICADO
google_oauth_live: PASSED
```

## Alcance

Se ejecuto un flujo OAuth real contra Google desde la interfaz de BITORA en staging local.

No se uso Postman.
No se cargo token manual.
No se marco PASSED con mocks.

## Entorno

```text
APP_ENV: staging
URL: http://localhost:8788
PostgreSQL: HEALTHY
App: HEALTHY
Worker: HEALTHY
Storage: HEALTHY
Safe Mode: ACTIVE
```

## Configuracion Google

```text
Redirect URI: http://localhost:8788/api/integrations/google/callback
Scopes solicitados: openid email profile
Proyecto Google: staging/test
Cuenta autorizada: gui***@gmail.com
```

Los valores sensibles no se documentan.

No se incluyen:

- Client Secret.
- authorization code.
- access_token.
- refresh_token.
- id_token.

## Flujo ejecutado

```text
BITORA
-> Configurar Evento
-> Google OAuth
-> Conectar Google
-> Google Account Chooser
-> Consentimiento real
-> Callback real en BITORA
-> Intercambio de code por tokens
-> Cifrado de tokens
-> Estado connected
```

## Validaciones realizadas

```text
OAuth iniciado desde BITORA: PASSED
Callback real recibido: PASSED
State validado: PASSED
Tokens recibidos: PASSED
Tokens cifrados: PASSED
Userinfo real contra Google: PASSED
Refresh real contra Google: PASSED
Desconexion/revocacion: PASSED
Reconexion: PASSED
Auditoria: PASSED
Aislamiento por organizacion/evento: PASSED
```

## Evidencia del gate live

Resultado de `verificar_google_oauth_multitenant_live.py` dentro del contenedor staging:

```json
{
  "mode": "live",
  "status": "passed",
  "checks": {
    "connected_integration": true,
    "provider": "google",
    "userinfo_live": true,
    "refresh_live": true,
    "token_encryption": true,
    "tokens_exposed": 0,
    "cross_event_assignments": 0,
    "audit_connected": true,
    "audit_tested": true,
    "audit_refreshed": true,
    "audit_disconnected": true,
    "account_email_masked": "gui***@gmail.com"
  }
}
```

## Evidencia BSTF Release

`run_bitora_supertest.py --release` dentro de staging registro:

```text
google_oauth_http_flow: PASSED
google_oauth_state_security: PASSED
google_oauth_multitenant_isolation: PASSED
google_oauth_refresh_contract: PASSED
google_oauth_backup_restore: PASSED
google_oauth_multitenant_live: PASSED
google_oauth_live: PASSED
```

## Correcciones realizadas durante la certificacion

### 1. Equivalencia de scopes Google

Google devuelve `email` y `profile` como scopes normalizados o como URLs oficiales:

```text
https://www.googleapis.com/auth/userinfo.email
https://www.googleapis.com/auth/userinfo.profile
```

BITORA ahora acepta esas equivalencias oficiales sin relajar la seguridad.

### 2. Sanitizacion de callback en logs

El callback OAuth puede incluir `code` en la query string. BITORA ahora redacta esa URL en el access log:

```text
/api/integrations/google/callback?[redacted]
```

## Seguridad

```text
Tokens expuestos: 0
Secretos expuestos: 0
Cruces de organizacion: 0
Callbacks mal asignados: 0
Eventos cruzados asignados: 0
```

## Auditoria

Se registraron acciones auditadas para:

```text
google_oauth.connect_started
google_oauth.connected
google_oauth.tested
google_oauth.refreshed
google_oauth.disconnected
google_oauth.connected
```

Los datos personales quedan enmascarados.

## Nota de seguridad operativa

El Client Secret utilizado para staging debe rotarse antes de cualquier uso prolongado o productivo, porque fue manipulado durante la configuracion asistida. No fue versionado en Git.

## Decision

```text
GOOGLE OAUTH LIVE CERTIFICADO
```

## Revalidacion Final Staging

Fecha: 2026-07-28

Identificador:

```text
FINAL-STAGING-REVALIDATION-20260728-1328
```

Resultado:

```text
google_oauth_multitenant_live: PASSED
google_oauth_live: PASSED en BSTF
organization_id: 3
integration_id: 5
account_email_masked: gui***@gmail.com
userinfo_live: PASSED
refresh_live: PASSED
refresh_before_userinfo: PASSED
token_encryption: PASSED
tokens_exposed: 0
cross_event_assignments: 0
```

La revalidacion renovo el access token vencido usando refresh token cifrado y luego ejecuto userinfo real contra Google.
