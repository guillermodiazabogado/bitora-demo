# BITORA Google OAuth Enablement - Current State

Fecha: 2026-07-21

Commit base:

```text
01c4cd9a509d5e9ba27393611718d66a2aef83e2
```

## Estado auditado

BITORA tenia preparada la arquitectura multi-tenant de integraciones, pero Google OAuth no tenia flujo HTTP completo.

## Modelo existente reutilizado

```text
organizations
organization_users
events.organization_id
organization_integrations
event_integrations
```

## Cifrado existente reutilizado

```text
IntegrationSecretService
BITORA_INTEGRATION_ENCRYPTION_KEY
```

## Permisos existentes

```text
integrations.view
integrations.create
integrations.edit
integrations.test
integrations.disable
event_integrations.view
event_integrations.assign
```

## Brecha original

Faltaba:

```text
endpoint de inicio OAuth
endpoint callback OAuth
state persistente de un solo uso
cliente Google desacoplado
exchange de authorization code
refresh
revocacion
desconexion
reconexion
UI minima
pruebas contract diferenciadas de live
```

## Gate previo

```text
google_oauth_live: OMITTED
```

Motivo: no habia flujo real contra Google iniciado desde BITORA.
