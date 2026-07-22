# BITORA WhatsApp Cloud API Setup Guide

## Objetivo

Activar WhatsApp Cloud API en staging para certificar `whatsapp_organization_live`.

## Requisitos Meta

```text
Meta App de prueba
WhatsApp Business Account de prueba
Phone Number ID
Business Account ID
Access Token
Verify Token definido por BITORA
App Secret
Telefono destinatario autorizado
Plantilla aprobada, si corresponde
```

No usar cuentas ni numeros de clientes reales para staging.

## Variables en deployment/staging/.env.staging

Completar el archivo real local. No versionarlo.

```text
BITORA_LIVE_INTEGRATIONS=true

WHATSAPP_PROVIDER=meta
WHATSAPP_ENABLED=true
WHATSAPP_ACCESS_TOKEN=<token_meta>
WHATSAPP_PHONE_NUMBER_ID=<phone_number_id>
WHATSAPP_BUSINESS_ACCOUNT_ID=<waba_id>
WHATSAPP_VERIFY_TOKEN=<verify_token_staging>
WHATSAPP_APP_SECRET=<app_secret>
WHATSAPP_API_VERSION=v22.0
WHATSAPP_SAFE_MODE=true
WHATSAPP_FORCE_RECIPIENT=<telefono_autorizado_con_codigo_pais>
WHATSAPP_TEST_RECIPIENT=<telefono_autorizado_con_codigo_pais>
WHATSAPP_REGISTRATION_TEMPLATE=<plantilla_aprobada_si_corresponde>
WHATSAPP_REGISTRATION_TEMPLATE_LANGUAGE=es_AR
WHATSAPP_REGISTRATION_TEMPLATE_VARIABLES=nombre,evento,portal
```

No compartir esos valores por chat.

## Flujo de prueba

1. Reiniciar app y worker de staging.
2. Verificar health de app, base y worker.
3. Crear o usar una organizacion de prueba.
4. Crear integracion WhatsApp provider `meta`.
5. Asignarla al evento de prueba para canal `whatsapp`.
6. Ejecutar envio desde BITORA.
7. Verificar que el worker procese el job.
8. Confirmar recepcion en el telefono autorizado.
9. Ejecutar:

```text
python verificar_whatsapp_multitenant_live.py
```

Si no hay webhook delivered/read, luego de confirmar visualmente la recepcion en el telefono se puede repetir con:

```text
WHATSAPP_LIVE_RECEIPT_CONFIRMED=true
```

Ese valor representa confirmacion manual del operador y debe quedar documentado en el reporte.

## Resultado esperado

```text
whatsapp_organization_live: PASSED
webhook_tenant_resolution_live: OMITTED
```

El webhook live se certifica en una fase separada con URL publica real.
