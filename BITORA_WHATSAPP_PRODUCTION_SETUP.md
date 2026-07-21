# BITORA - Configuracion WhatsApp Cloud API

## Requisitos Meta

1. Crear o usar una app en Meta Developers.
2. Agregar producto WhatsApp.
3. Asociar WhatsApp Business Account.
4. Obtener:
   - Access Token productivo.
   - Phone Number ID.
   - Business Account ID.
   - App Secret.
5. Crear un Verify Token propio para el webhook.
6. Aprobar plantillas operativas en Meta.

## Variables

```env
WHATSAPP_PROVIDER=meta
WHATSAPP_ENABLED=true
WHATSAPP_ACCESS_TOKEN=...
WHATSAPP_PHONE_NUMBER_ID=...
WHATSAPP_BUSINESS_ACCOUNT_ID=...
WHATSAPP_VERIFY_TOKEN=...
WHATSAPP_APP_SECRET=...
WHATSAPP_SAFE_MODE=false
WHATSAPP_MAX_RETRIES=3
WHATSAPP_TIMEOUT_SECONDS=15
WHATSAPP_REGISTRATION_TEMPLATE=nombre_plantilla_aprobada
WHATSAPP_REGISTRATION_TEMPLATE_LANGUAGE=es_AR
WHATSAPP_REGISTRATION_TEMPLATE_VARIABLES=nombre,evento,portal
```

## Webhook

URL:

```text
https://TU_DOMINIO/api/communications/whatsapp/webhook
```

Verificacion:

- `hub.verify_token` debe coincidir con `WHATSAPP_VERIFY_TOKEN`.
- Los POST deben incluir `X-Hub-Signature-256`.
- En `APP_ENV=production`, si falta `WHATSAPP_APP_SECRET`, BITORA marca configuracion no apta.

## Modo seguro

Para pruebas controladas:

```env
WHATSAPP_SAFE_MODE=true
WHATSAPP_FORCE_RECIPIENT=549XXXXXXXXXX
```

En modo seguro, los envios reales se redirigen al telefono forzado. No usarlo como produccion final.

## Plantillas

La confirmacion de inscripcion usa plantilla si:

- `template_code = registration_confirmation`
- `WHATSAPP_REGISTRATION_TEMPLATE` esta configurada.

Si no hay plantilla, BITORA intenta texto libre, que Meta solo acepta dentro de ventana de conversacion abierta. Para mensajes iniciados por la plataforma usar plantillas aprobadas.

## Validacion final

Ejecutar:

```text
verificar_v7_whatsapp_productivo.py
verificar_comunicaciones_permisos.py
verificar_integridad_bitora.py
verificar_convivencia_modulos.py
```
