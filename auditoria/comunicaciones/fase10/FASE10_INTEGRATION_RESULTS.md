# Fase 10 - Resultados de integracion

## Infraestructura

- Staging `/ready`: HTTP 200.
- Entorno: staging.
- Migraciones: 55/55.
- Deployment posterior a la rotacion OAuth: `bd33c9de-2396-4d4e-a96a-d5a20d00a02d` SUCCESS.
- Produccion 1.0.0: saludable e intacta.

## Flujo de inscripcion

El flujo crea acreditacion, consentimiento y colas de email/WhatsApp solamente para una inscripcion publica nueva. La acreditacion observada fue creada por `phase9-admin`; por diseño no invoco `queue_registration_confirmation()`. Por eso no dejo filas de cola: no fue un fallo de Gmail, Meta ni PostgreSQL. Las altas administrativas requieren reenvio individual o un cambio funcional explicito si se desea notificarlas automaticamente.

## Defecto detectado; primer experimento rechazado

El worker marca como `completed` un handler de comunicaciones que retorna `ok=false`. Esto puede dejar la comunicacion pendiente sin reintento automatico.

- Experimento: `0bc1a901f94641fe7ba13112c4adc10721ebf959`.
- Resultado QA: **REJECTED**. Reintentar todo estado pendiente puede duplicar mensajes si el proveedor acepto la solicitud pero la respuesta se perdio.
- Reversion local: `d1fd74856b564e8d5c892924ba304a5f696cced6`.
- No se desplego ningun cambio de worker.
- Correccion requerida: clasificar `retryable` pre-envio frente a `ambiguous` post-envio; los ambiguos deben quedar `UNKNOWN` y reconciliarse mediante identificador/webhook, sin reintento ciego.

## Flujo integrado

- Email: **PASS**. Se ejecuto una inscripcion publica sintetica con consentimiento de email. La cola paso de `pending` a `enviado` en un intento, Gmail devolvio identificador y el mensaje `[SAFE] Inscripcion confirmada` fue recibido en el buzon autorizado.
- WhatsApp: **PASS funcional**. Meta acepto el mensaje real, devolvio identificador y el destinatario confirmo manualmente su recepcion el 2026-11-13. Falta el evento automatico `delivered` porque la WABA compartida no tiene una app suscripta a webhooks.
- Flujo conjunto: **PASS funcional** para inscripcion, Gmail y WhatsApp. La trazabilidad automatica de entrega WhatsApp permanece **BLOCKED**.
