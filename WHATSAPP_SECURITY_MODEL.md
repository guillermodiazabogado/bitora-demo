# BITORA WhatsApp Security Model

## Principios

```text
No exponer tokens.
No enviar a destinatarios libres en staging.
No usar integraciones de otra organizacion.
No marcar live sin proveedor real.
No procesar webhooks sin validacion.
```

## Safe Mode

En staging, WhatsApp debe operar con:

```text
WHATSAPP_SAFE_MODE=true
WHATSAPP_FORCE_RECIPIENT=<telefono_controlado>
```

La jerarquia efectiva es:

```text
Safe Mode global
Safe Mode organizacion
Safe Mode evento
```

Si Safe Mode esta activo, BITORA sustituye el destinatario original por el telefono forzado y registra la accion en auditoria.

## Aislamiento multi-tenant

Cada envio debe conservar:

```text
organization_id
event_id
integration_id
channel=whatsapp
```

El endpoint de asignacion `event_integrations` rechaza integraciones que no pertenecen a la organizacion del evento.

## Secretos

Los tokens se tratan como secretos:

```text
WHATSAPP_ACCESS_TOKEN
WHATSAPP_APP_SECRET
WHATSAPP_VERIFY_TOKEN
```

No deben aparecer en:

```text
frontend
respuestas API
logs
auditoria
reportes
backups en texto plano
```

Los errores de Meta se sanitizan antes de salir del proveedor.

## Idempotencia

La cola usa clave idempotente por:

```text
event_id
person_id
accreditation_id
template
subject
recipient
```

Esto evita duplicados generados por doble click o reintentos internos antes del envio.

## Webhooks

El endpoint existe:

```text
POST /api/communications/whatsapp/webhook
GET /api/communications/whatsapp/webhook
```

El `GET` valida el verify token de Meta.

El `POST` valida firma cuando `WHATSAPP_APP_SECRET` esta configurado y normaliza:

```text
sent
delivered
read
failed
incoming messages
```

La certificacion live de webhooks requiere URL publica real y evidencia recibida desde Meta.
