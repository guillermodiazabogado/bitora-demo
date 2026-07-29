# BITORA_V4_LIVE_INTEGRATIONS_ROOT_CAUSE_REPORT

Fecha: 2026-07-29

Rama de trabajo: `fix/v4-final-live-integrations`

Base: `991e8e91f8a83e87d4dbb202131f98619e1e64b8`

## Resumen

Los gates live finales no fallan por V4.10 ni por una regresion funcional local.

La ejecucion BSTF release dentro de staging Docker quedo bloqueada por dependencias live externas:

- Meta Cloud API rechaza el token WhatsApp configurado: `OAuthException`, codigo `190`.
- Webhook live no tiene URL publica configurada en `WHATSAPP_WEBHOOK_PUBLIC_URL`.
- GitHub CLI local no esta autenticado: token local invalido.

Durante el diagnostico tambien se encontro y corrigio un defecto de contrato:

- Con Live Mode desactivado, el proveedor demo no normalizaba payloads webhook de Meta.
- Eso rompia los verificadores contract `verificar_whatsapp_webhook_*`.
- La correccion fue mover la normalizacion Meta a una funcion comun, usada tambien cuando el proveedor activo es demo.

No se deben declarar `PASSED`, crear tag `v4.0.0` ni publicar GitHub Release hasta resolver estas dependencias y repetir BSTF release.

## whatsapp_multitenant_live

- Resultado previo: FAILED en BSTF release final.
- Error exacto: Meta Cloud API HTTP 401 con `OAuthException`, codigo `190`.
- Ruta de ejecucion: `run_bitora_supertest.py --release` dentro de `bitora-staging-app`, caso `verificar_whatsapp_multitenant_live.py`.
- Causa raiz: token de acceso WhatsApp configurado en staging vencido, revocado, invalido o no aceptado por Meta.
- Riesgo: no se puede demostrar envio live controlado desde BITORA hacia Meta.
- Archivos afectados: no se confirma defecto de codigo; depende de `deployment/staging/.env.staging`, no versionado.
- Cambio minimo requerido: cargar un `WHATSAPP_ACCESS_TOKEN` valido en `.env.staging`, recrear/reiniciar app y worker, y repetir el verificador live.
- Prueba de regresion necesaria: `python verificar_whatsapp_multitenant_live.py` en staging Docker con Safe Mode ON, Live Mode controlado y destinatario autorizado.

## webhooks_multitenant_live

- Resultado previo: FAILED en BSTF release final.
- Error exacto live: evidencia previa paso historicamente, pero la corrida final no pudo sostener el flujo live; `webhook_tenant_resolution_live` quedo OMITTED.
- Error exacto contract corregido: `IndexError: list index out of range` porque el proveedor demo devolvia cero eventos normalizados.
- Ruta de ejecucion: `run_bitora_supertest.py --release` dentro de `bitora-staging-app`, casos `verificar_webhooks_multitenant_live.py` y gate `webhook_tenant_resolution_live`.
- Causa raiz live: no hay URL publica activa configurada en `WHATSAPP_WEBHOOK_PUBLIC_URL` dentro del contenedor.
- Causa raiz contract: la normalizacion webhook estaba acoplada al proveedor Meta activo y no disponible con proveedor demo.
- Riesgo: Meta no puede verificar ni entregar webhooks reales a BITORA.
- Archivos afectados: `backend/services/whatsapp.py` para contrato; configuracion local no versionada para live.
- Cambio minimo requerido: abrir tunnel HTTPS temporal al endpoint real del webhook, configurar la URL en Meta Developers, cargar `WHATSAPP_WEBHOOK_PUBLIC_URL` en `.env.staging`, reiniciar app/worker y repetir el verificador live.
- Prueba de regresion necesaria: `python verificar_webhooks_multitenant_live.py` con POST real de Meta, firma valida, idempotencia y tenant resolution.

Pruebas contract ejecutadas despues de la correccion:

- `verificar_whatsapp_webhook_contract.py`: PASSED.
- `verificar_whatsapp_webhook_signature.py`: PASSED.
- `verificar_whatsapp_webhook_multitenant.py`: PASSED.
- `verificar_whatsapp_webhook_idempotency.py`: PASSED.

## whatsapp_organization_live

- Resultado previo: FAILED como consecuencia del fallo de `whatsapp_multitenant_live`.
- Error exacto: el envio WhatsApp live no llega a estado enviado por rechazo 401 de Meta.
- Ruta de ejecucion: gate agregado por BSTF desde evidencia live WhatsApp.
- Causa raiz: token Meta invalido o vencido.
- Riesgo: no se puede certificar ownership organization/event/integration sobre un envio live actual.
- Archivos afectados: no se confirma defecto de codigo.
- Cambio minimo requerido: resolver token Meta y repetir la prueba live.
- Prueba de regresion necesaria: verificar que `organization_id`, `event_id` e `integration_id` coinciden y que los cruces multi-tenant son 0.

## webhook_tenant_resolution_live

- Resultado previo: OMITTED.
- Error exacto: falta `WHATSAPP_WEBHOOK_PUBLIC_URL`.
- Ruta de ejecucion: gate BSTF derivado de evidencia `webhooks_multitenant_live`.
- Causa raiz: no existe tunnel publico activo ni URL configurada en staging.
- Riesgo: no se puede certificar resolucion tenant-aware de webhooks reales.
- Archivos afectados: configuracion local no versionada y Meta Developers.
- Cambio minimo requerido: configurar URL publica HTTPS real, verify token y suscripcion `messages` en Meta.
- Prueba de regresion necesaria: recibir webhook real de Meta, validar `X-Hub-Signature-256`, resolver `integration_id`, `organization_id`, `event_id`, actualizar estado y bloquear replay.

## Acciones manuales requeridas

1. GitHub CLI:
   - Ejecutar fuera del repo o desde terminal:
     `gh auth logout -h github.com -u guillermodiazabogado`
   - Luego:
     `gh auth login -h github.com -p https -w`
   - Verificar:
     `gh auth status`

2. Meta WhatsApp:
   - Generar un access token valido para la app/WABA de staging.
   - Cargarlo localmente en `deployment/staging/.env.staging` como `WHATSAPP_ACCESS_TOKEN`.
   - No pegar el token en chat ni versionarlo.

3. Webhook publico:
   - Abrir un tunnel HTTPS temporal hacia el staging local.
   - Cargar la URL completa del endpoint webhook en `WHATSAPP_WEBHOOK_PUBLIC_URL`.
   - Configurar la misma URL en Meta Developers, WhatsApp Webhooks, campo `messages`.
   - Mantener `WHATSAPP_VERIFY_TOKEN` y `WHATSAPP_APP_SECRET` locales y no versionados.

## Frase para reanudar

`listo gh meta webhook`

Al reanudar, continuar desde la repeticion de:

- `verificar_whatsapp_multitenant_live.py`
- `verificar_webhooks_multitenant_live.py`
- `run_bitora_supertest.py --release`
