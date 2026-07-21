# BITORA - Arquitectura WhatsApp Productivo

## Estado

BITORA integra WhatsApp Business Platform mediante Meta Cloud API como canal del Centro de Comunicaciones. El frontend nunca se conecta con Meta: crea comunicaciones, el backend valida permisos, consentimiento y destinatarios, y la cola procesa los envios.

## Flujo de salida

1. Usuario autorizado crea o envia una comunicacion.
2. Backend valida evento activo, rol y permiso `communications.*`.
3. Se resuelve la audiencia del evento.
4. Se valida telefono, consentimiento y supresion.
5. Se crea registro en `communication_queue`.
6. El worker ejecuta `whatsapp.send`.
7. `WhatsAppProvider` envia a Meta Cloud API.
8. Meta responde con `message_id`.
9. Webhook actualiza estados.
10. Historial, metricas y auditoria quedan registrados.

## Flujo de entrada

1. Meta envia webhook firmado.
2. BITORA verifica `X-Hub-Signature-256` cuando `WHATSAPP_APP_SECRET` esta configurado.
3. El payload se normaliza con `WhatsAppProvider.normalize_webhook`.
4. Los estados se guardan en `whatsapp_delivery_events`.
5. Los mensajes entrantes se guardan en `communication_assistant_history`.
6. No se responde automaticamente; queda preparado para bandeja/conversaciones futuras.

## Tablas

- `communication_queue`: cola unificada email/WhatsApp.
- `communication_logs`: historial operativo.
- `whatsapp_delivery_events`: eventos idempotentes de Meta.
- `whatsapp_suppressions`: telefonos bloqueados por opt-out o error proveedor.
- `communication_assistant_history`: mensajes entrantes y futuras respuestas asistidas.
- `audit_logs`: trazabilidad de acciones y webhooks.

## Seguridad

- No se usan librerias no oficiales ni WhatsApp Web.
- No se exponen tokens al frontend.
- El webhook POST se firma con `WHATSAPP_APP_SECRET`.
- En produccion real `WHATSAPP_SAFE_MODE` debe estar desactivado.
- En demo/control se puede activar `WHATSAPP_SAFE_MODE=true` y forzar destinatario.
- Los permisos de configuracion se limitan a `communications.manage_providers`.

## Compatibilidad

Funciona con SQLite para demo/local y queda migrable a PostgreSQL mediante `013_whatsapp_production.sql`.
