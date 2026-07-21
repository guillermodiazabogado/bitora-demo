# BITORA Google OAuth Security Model

## Principios

```text
No confiar en parametros del callback salvo state.
No guardar tokens en texto plano.
No exponer secretos en API.
No registrar authorization code.
No permitir cruces entre organizaciones.
```

## State

El state se guarda en `google_oauth_states` y contiene:

```text
organization_id
integration_id
user_id
actor
nonce_hash
expires_at
status
```

Propiedades:

```text
aleatorio
no predecible
un solo uso
con vencimiento
asociado a organizacion
asociado a integracion
asociado a usuario
```

## Tokens

Se guardan cifrados en:

```text
organization_integrations.configuration_encrypted
```

Metadata permitida:

```text
account_email
account_id
requested_scopes
granted_scopes
connected_at
expires_at
last_refresh_at
last_revoked_at
oauth_status
```

## Permisos

```text
integrations.view
integrations.create
integrations.test
integrations.disable
integrations.google_connect
integrations.google_disconnect
integrations.google_refresh
event_integrations.assign
```

## Auditoria

Acciones auditadas:

```text
google_oauth.connect_started
google_oauth.connected
google_oauth.error
google_oauth.tested
google_oauth.test_failed
google_oauth.refreshed
google_oauth.refresh_failed
google_oauth.disconnected
google_oauth.revoke_failed
```
