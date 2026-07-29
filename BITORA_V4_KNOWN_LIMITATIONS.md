# BITORA_V4_KNOWN_LIMITATIONS

Fecha: 2026-07-29

## Limitaciones conocidas no bloqueantes para desarrollo

- Endurance 24h no ejecutado.
- BSTF final detecto deuda tecnica `medium` y `low`, principalmente tamanos de funciones y duplicacion de helpers.
- GitHub CLI local tiene token invalido; la PR se creo por navegador y el merge se publico por Git.

## Bloqueos para release estable

- `whatsapp_multitenant_live`: FAILED en BSTF release final.
- `webhooks_multitenant_live`: FAILED en BSTF release final.
- `whatsapp_organization_live`: FAILED en BSTF release final.
- `webhook_tenant_resolution_live`: OMITTED en BSTF release final.

## Accion requerida

Reactivar o corregir evidencia live de WhatsApp/Webhooks en staging y repetir BSTF release.
