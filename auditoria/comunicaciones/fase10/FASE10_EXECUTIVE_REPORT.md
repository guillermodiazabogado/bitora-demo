# BITORA 5.8.2 - Fase 10 comunicaciones

## Estado: BLOCKED

La infraestructura y ambos proveedores fueron auditados sin tocar produccion. Gmail supera los gates de confianza OAuth, autorizacion y entrega real. WhatsApp supera configuracion y entrega funcional: el propietario confirmo manualmente la recepcion del mensaje el 2026-11-13.

El propietario otorgo manualmente el scope minimo `gmail.send` a la cuenta remitente. El secreto se actualizo sin exponerse, Railway redeployo staging y la prueba directa mas una inscripcion publica sintetica fueron recibidas correctamente en Gmail.

WhatsApp tiene numero conectado, calidad alta y plantilla aprobada. Una inscripcion real con destinatario autorizado revelo un defecto de normalizacion del formato argentino local de 10 digitos; se corrigio en `d90b2b3`, se desplego y Meta acepto el mensaje. La cola quedo `enviado` sin error.

La trazabilidad automatica `delivered` sigue bloqueada: la WABA no tiene una app suscripta al webhook y staging comparte todos los recursos Meta sensibles con produccion. No se modifico esa suscripcion para evitar impacto productivo. Este bloqueo ya no invalida la entrega funcional confirmada, pero impide cerrar la observabilidad automatica.

Adicionalmente se detecto un defecto de reintentos: los fallos de proveedor podian dejar la comunicacion pendiente mientras el job quedaba completado. El primer experimento `0bc1a90` fue rechazado por QA porque un reintento ciego tras un timeout ambiguo puede duplicar mensajes. Fue revertido en `d1fd748`; no se desplego.

Produccion permanece saludable e intacta. No hubo push, merge, migraciones ni secretos expuestos.

## Para continuar

1. Crear recursos Meta aislados para staging o autorizar formalmente el cambio de webhook sobre la WABA compartida.
2. Implementar y validar una clasificacion segura entre fallos reintentables y resultados ambiguos antes de autorizar un despliegue.

La inscripcion sintetica y la recepcion por Gmail y WhatsApp ya fueron verificadas. La fase permanece bloqueada solo para el cierre operativo completo hasta resolver la trazabilidad automatica y el manejo seguro de resultados ambiguos sin reintentos ciegos.
