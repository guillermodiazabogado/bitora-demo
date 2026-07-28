# BITORA WhatsApp Webhook Live Current State

Fecha: 2026-07-28

## Estado actual

```text
WhatsApp Live: CERTIFICADO
whatsapp_organization_live: PASSED
webhook_tenant_resolution_live: PASSED
```

## Endpoint real

```text
GET  /api/communications/whatsapp/webhook
POST /api/communications/whatsapp/webhook
```

## Verificacion GET

BITORA valida:

```text
hub.mode = subscribe
hub.verify_token = WHATSAPP_VERIFY_TOKEN
hub.challenge devuelto como text/plain
```

Resultado esperado:

```text
Token correcto: HTTP 200 + challenge
Token incorrecto: HTTP 403
```

## Recepcion POST

BITORA valida:

```text
X-Hub-Signature-256
HMAC SHA-256
WHATSAPP_APP_SECRET
cuerpo crudo del request
comparacion constante
```

Si la firma no coincide:

```text
HTTP 403
No se procesa payload
```

## Procesamiento WhatsApp

El proveedor Meta normaliza:

```text
statuses: sent, delivered, read, failed
incoming messages
message_id
phone_number_id
timestamp
errors
```

BITORA resuelve estados por:

```text
provider_message_id -> communication_queue
communication_queue -> event_id
communication_queue -> organization_id
communication_queue -> integration_id
```

## Idempotencia

Se usa:

```text
provider + external_event_id
```

para evitar reprocesar eventos duplicados.

## Endurecimiento incorporado

```text
No retroceder estados fuera de orden.
Auditoria con event_id, organization_id e integration_id.
Webhook unresolved auditado sin actualizar registros.
```

## Certificacion live ejecutada

Flujo certificado:

```text
Meta -> URL publica temporal -> BITORA -> estado actualizado
```

Resultado:

```text
Meta challenge: PASSED
Meta POST real: PASSED
Firma valida: PASSED
Evento recibido: delivered
Tenant resolution: PASSED
Auditoria: PASSED
Idempotencia: PASSED
Cruces multi-tenant: 0
Secretos expuestos: 0
```

Evidencia sanitizada:

```text
message_id: wamid***DNAA=
queue_id: 165
job_id: 23
organization_id: 1
event_id: 147
integration_id: 30
```

Nota: la URL publica utilizada fue temporal mediante Cloudflare Tunnel. Para produccion se requiere URL HTTPS estable.
