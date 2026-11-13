# Fase 10 - WhatsApp Meta Cloud API

## Resultado

- Configuracion Meta: **PASS**.
- Envio real: **PASS (aceptado por Meta)**.
- Entrega al destinatario: **PASS**, confirmada manualmente por el propietario el 2026-11-13.
- Trazabilidad automatica `delivered`: **BLOCKED** por ausencia de webhook.

## Evidencia verificada

- Meta Cloud API conectada.
- Numero emisor: CONNECTED, calidad GREEN, plataforma CLOUD_API.
- WABA y Phone Number ID presentes sin exponer valores sensibles.
- Permisos de mensajeria y administracion disponibles.
- Plantilla `bitora_confirmacion_inscripcion`: APPROVED, `es_AR`, tres parametros posicionales.
- Backend envia exactamente tres parametros para esa plantilla.
- Normalizacion argentina en el SHA de staging: `011...`, `5411...` y `54911...` convergen al formato movil E.164; otros codigos de area ensayados tambien preservan el area.
- Webhook registra estados `sent`, `delivered`, `read` y `error` de forma idempotente por evento externo.

## Prueba real del 2026-11-13

- El propietario autorizo un numero distinto del emisor y se realizo una inscripcion publica sintetica con consentimiento.
- Se detecto que el formato local argentino de 10 digitos no era convertido a `549...`.
- Correccion local `d90b2b3`: normaliza numeros argentinos locales de 10 digitos; 5/5 pruebas unitarias PASS.
- Primer intento: rechazo pre-envio HTTP 400 sin identificador de mensaje; fue seguro reintentarlo.
- Segundo intento: Meta acepto el template, devolvio identificador y la cola quedo `enviado`, intento 2, sin error.
- El destinatario confirmo por un canal independiente que el WhatsApp llego correctamente.
- Staging quedo saludable en deployment `72cfa30f-33c1-4217-8940-d2f5dcb50ab9`, imagen `sha256:9feffac7bf363ba8b2bf377cf72f1b252b5f6709304596aa76ee5133adcc4e62`.

## Diagnostico de entrega

- No ingreso trafico al endpoint webhook de staging y la cola no avanzo a `entregado`.
- La consulta autenticada de Meta informa cero aplicaciones suscriptas en la WABA.
- La comparacion segura de configuracion confirma que staging comparte WABA, Phone Number ID, access token y app secret con produccion.
- Suscribir o cambiar la app sobre esa WABA puede afectar el flujo productivo; no se realizo ese cambio.

## Diagnostico del intento anterior

El HTTP 400/code 100 historico uso el mismo numero emisor. La prueba actual utilizo un destinatario autorizado distinto y demostro aceptacion por Meta tras corregir el formato local.

## Accion pendiente

Aislar una WABA/numero/app para staging o aprobar formalmente la configuracion del webhook sobre el recurso Meta compartido. La entrega funcional ya fue confirmada; el pendiente es la trazabilidad automatica del estado `delivered`.
