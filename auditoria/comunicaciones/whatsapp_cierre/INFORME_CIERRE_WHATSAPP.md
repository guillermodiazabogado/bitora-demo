# BITORA 5.8.2 - Cierre tecnico de WhatsApp

Fecha: 2026-11-13

## Estado

- Rama: `fix/5.8.2-whatsapp-traceability-idempotency`.
- SHA candidato de codigo: `06408c96fdc0dab59a101ff85ec1b8849c0b10c6`.
- Estado: **IMPLEMENTED + TESTED**.
- Staging: **NOT DEPLOYED / NOT VERIFIED** para este SHA.
- Produccion: saludable, version declarada 1.0.0 e intacta.
- Migraciones nuevas: ninguna.

## Diagnostico confirmado

1. Dos jobs distintos podian procesar simultaneamente la misma fila de WhatsApp porque el envio ocurria antes de cualquier claim transaccional.
2. Timeouts, desconexiones y errores HTTP se reducian al mismo resultado generico; un resultado posiblemente aceptado podia quedar listo para reintento.
3. El worker completaba el job aunque el handler devolviera un resultado pendiente.
4. Un webhook `failed` tardio podia degradar un mensaje ya entregado o leido.
5. Staging podia aceptar un webhook sin firma si faltaba `WHATSAPP_APP_SECRET`.

## Cambios implementados

- Claim atomico persistente `pendiente -> enviando`; una segunda replica no vuelve a enviar la misma fila.
- Estados seguros `enviando` y `desconocido`; un timeout o HTTP 5xx ambiguo no se reintenta automaticamente.
- Reintento automatico limitado a rechazo inequivoco y seguro, como HTTP 429 o fallo comprobado previo a transmitir.
- Correlacion opaca `biz_opaque_callback_data` para que un webhook tardio pueda reconciliar un resultado desconocido sin incluir datos personales.
- Maquina de estados monotona: `sent`, `delivered`, `read` y `failed` fuera de orden no degradan evidencia superior.
- Firma HMAC-SHA256 fail-closed cuando falta el secreto.
- Recuperacion tras reinicio: claims y jobs WhatsApp abandonados pasan a reconciliacion segura, nunca a reenvio ciego.
- Resolucion administrativa individual y auditada para confirmar no envio, asociar un message id o marcar fallo.
- Telefonos en auditoria y respuestas generales enmascarados.

## Pruebas ejecutadas

- Suite focalizada: 19/19 PASS.
- Normalizacion telefonica: incluida en las 19 pruebas, PASS.
- PostgreSQL 16 real, esquema completo y dos procesos independientes sobre el mismo `queue_id`: PASS; una sola llamada al proveedor, un solo intento persistido.
- Regresion WhatsApp inteligente: PASS.
- Regresion WhatsApp productivo, cola, firma, webhook e idempotencia: PASS.
- Contratos webhook multitenant: PASS local; ejecucion live omitida por ausencia deliberada de secretos en el contenedor de prueba.
- Idempotencia de inscripcion y recuperacion de respuesta perdida: PASS.
- Seleccion de destinatario de confirmacion: PASS.

No se enviaron mensajes reales adicionales y no se utilizo ningun numero personal.

## Gate externo pendiente

El codigo no fue desplegado porque el mandato exige autorizacion previa. Ademas, la WABA compartida no tiene una app suscripta a webhooks. Para pasar de TESTED a STAGING-VERIFIED se requiere:

1. Autorizar despliegue del SHA candidato en staging.
2. Configurar una app/WABA de staging aislada, o autorizar formalmente la suscripcion de webhook sobre el recurso compartido evaluando el impacto en produccion.
3. Ejecutar un unico envio autorizado y observar `sent/delivered` firmado, duplicado idempotente y reconciliacion en PostgreSQL.

No se realizo push, merge, despliegue ni cambio de costos.
