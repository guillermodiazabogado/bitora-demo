# BITORA WhatsApp Webhook Setup Guide

Fecha: 2026-07-28

## Ruta BITORA

```text
/api/communications/whatsapp/webhook
```

## Variables

Configurar en `deployment/staging/.env.staging`:

```text
WHATSAPP_WEBHOOK_ENABLED=true
WHATSAPP_WEBHOOK_PUBLIC_URL=https://<url-temporal>/api/communications/whatsapp/webhook
WHATSAPP_APP_ID=<app id de Meta>
WHATSAPP_VERIFY_TOKEN=<valor local>
WHATSAPP_APP_SECRET=<valor local>
BITORA_LIVE_INTEGRATIONS=true
```

No versionar `.env.staging`.

## Meta Developers

En la app de Meta:

```text
WhatsApp
Configuracion
Webhooks
```

Cargar:

```text
Callback URL: WHATSAPP_WEBHOOK_PUBLIC_URL
Verify Token: WHATSAPP_VERIFY_TOKEN
```

Suscribir solamente:

```text
messages
```

## Secuencia Validada

La certificacion live uso este orden:

```text
1. Verificar localmente el challenge GET.
2. Crear tunel HTTPS temporal.
3. Registrar la suscripcion Webhooks de la app para whatsapp_business_account/messages.
4. Suscribir el WABA a la app.
5. Configurar override_callback_uri del WABA hacia la URL temporal.
6. Enviar mensaje desde BITORA y esperar POST real de Meta.
```

Si Meta devuelve `(#100) Before override the current callback uri...`, falta el paso de suscripcion Webhooks de la app para `whatsapp_business_account/messages`.

## Tunel

Usar un tunel temporal solo para staging.

La opcion recomendada es:

```text
Cloudflare Tunnel
```

El tunel apunta a un proxy local que solo permite:

```text
/api/communications/whatsapp/webhook
```

No usar esta URL temporal como URL productiva.
