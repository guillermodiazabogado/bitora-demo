# BITORA WhatsApp Webhook Security Model

Fecha: 2026-07-28

## Principios

```text
No confiar en organization_id por query string.
No confiar en headers no firmados para tenant.
No procesar POST sin firma valida.
No registrar secretos.
No registrar payload completo en reportes.
```

## Firma

Meta envia:

```text
X-Hub-Signature-256
```

BITORA calcula:

```text
HMAC_SHA256(raw_body, WHATSAPP_APP_SECRET)
```

y compara en tiempo constante.

## Resolucion tenant-aware

Para estados salientes:

```text
message_id
-> communication_queue.provider_message_id
-> queue_id
-> event_id
-> organization_id
-> integration_id
```

Si no se encuentra `message_id`:

```text
No se actualiza comunicacion.
Se registra evento unresolved sanitizado.
```

## Idempotencia

La clave de idempotencia es:

```text
provider + external_event_id
```

Los reintentos de Meta no duplican cambios.

## Datos sensibles

No se deben guardar en reportes:

```text
Access Token
App Secret
Verify Token
payload completo
telefonos completos
```
