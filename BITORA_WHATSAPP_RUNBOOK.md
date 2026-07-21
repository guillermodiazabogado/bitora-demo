# BITORA - Runbook WhatsApp

## Verificar estado

1. Entrar como Super Admin o Soporte autorizado.
2. Abrir `Diagnostico Tecnico`.
3. Revisar tarjeta WhatsApp.
4. Abrir `Comunicaciones` y revisar proveedor, modo seguro, ultimo error y cola.

## Error: proveedor no configurado

Revisar variables:

- `WHATSAPP_ENABLED=true`
- `WHATSAPP_PROVIDER=meta`
- `WHATSAPP_ACCESS_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID`
- `WHATSAPP_BUSINESS_ACCOUNT_ID`
- `WHATSAPP_VERIFY_TOKEN`
- `WHATSAPP_APP_SECRET`

## Error: webhook no valida

1. Confirmar URL publica HTTPS.
2. Confirmar que Meta usa `/api/communications/whatsapp/webhook`.
3. Confirmar `WHATSAPP_VERIFY_TOKEN`.
4. Confirmar `WHATSAPP_APP_SECRET`.
5. Revisar logs tecnicos sin exponer secretos.

## Error: mensaje rechazado por Meta

1. Revisar que el telefono este en formato internacional, por ejemplo `5492994522126`.
2. Revisar consentimiento WhatsApp.
3. Revisar si el telefono esta en `whatsapp_suppressions`.
4. Si es comunicacion iniciada por BITORA, usar plantilla aprobada.
5. Revisar `communication_queue.last_error`.

## Demo controlada

Para mostrar el flujo sin contactar audiencia real:

```env
WHATSAPP_SAFE_MODE=true
WHATSAPP_FORCE_RECIPIENT=549XXXXXXXXXX
```

Al terminar la prueba, volver a revisar colas y logs.

## Produccion real

Antes de operar con asistentes reales:

- `WHATSAPP_SAFE_MODE=false`
- Plantillas aprobadas.
- Consentimiento capturado.
- Webhook verificado.
- Prueba individual exitosa.
- Backup reciente.
