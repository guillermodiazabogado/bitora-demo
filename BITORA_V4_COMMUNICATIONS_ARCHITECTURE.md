# BITORA V4 Communications Architecture

## Canales

Email, WhatsApp, notificaciones internas y futuras push.

## Contrato Minimo

Toda comunicacion debe tener organizacion, evento, actor, destinatario, motivo, template, estado e idempotency key.

## Flujo

Crear contenido, seleccionar segmento, previsualizar, aprobar si corresponde, programar o enviar, procesar por job, recibir estado, auditar.

## Seguridad

Safe Mode se evalua por plataforma, organizacion y evento. El frontend no puede desactivarlo. Integracion ajena nunca puede usarse.

## Estados

`draft`, `pending_approval`, `scheduled`, `queued`, `sending`, `sent`, `delivered`, `failed`, `cancelled`, `restored_inactive`.

## Criterios

- Campanas masivas requieren permiso especial.
- Reenvio individual separado de envio masivo.
- Jobs idempotentes.
- Secretos y payloads sensibles no aparecen en logs.
