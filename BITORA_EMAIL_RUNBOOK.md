# BITORA - Runbook Email

## Proveedor Caido

1. No reintentar manualmente en masa.
2. Verificar panel del proveedor.
3. Pausar envios grandes.
4. Mantener QR/inscripcion operativos.
5. Reanudar cuando el proveedor recupere.

## Cola Detenida

1. Revisar Diagnostico Tecnico.
2. Ver pendientes/error en Centro de Comunicaciones.
3. Verificar `EMAIL_ENABLED`.
4. Verificar jobs/workers si aplica.
5. Reintentar solo fallidos transitorios.

## Rebotes Altos

1. Detener envios no esenciales.
2. Revisar origen de audiencia.
3. Exportar fallidos.
4. Limpiar emails invalidos.
5. Mantener supresion activa.
6. No insistir sobre hard bounces.

## Quejas / Spam

1. Suspender comunicaciones promocionales.
2. Revisar contenido y consentimiento.
3. Confirmar baja/supresion.
4. Revisar DNS y reputacion.
5. No reenviar a personas con complaint.

## Webhook Fallando

1. Verificar URL publica.
2. Confirmar HTTPS.
3. Confirmar `EMAIL_WEBHOOK_SECRET`.
4. Revisar firma Svix.
5. Enviar evento de prueba desde proveedor.

## Dominio No Verificado

1. Revisar registros DNS.
2. Esperar propagacion.
3. Confirmar SPF/DKIM/DMARC.
4. No habilitar envios reales hasta que el proveedor lo marque verificado.

## Cancelacion Urgente

1. Pausar/cancelar cola pendiente desde Comunicaciones.
2. No intentar retirar emails ya enviados.
3. Auditar la accion.
4. Informar a produccion.

## Rotacion De API Key

1. Crear nueva key.
2. Cargar variable en Render/Railway.
3. Reiniciar servicio.
4. Enviar prueba.
5. Revocar key anterior.
6. Auditar cambio.
