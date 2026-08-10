# BITORA Participant Notification Inbox

## Objetivo

V4.0.3 centraliza en una bandeja simple los avisos que el participante necesita para vivir el evento activo.

## Fuentes

La bandeja se arma con datos ya disponibles en el payload del portal:

- anuncios publicados del evento;
- comunicaciones registradas para el participante y evento;
- reservas activas del participante;
- certificados disponibles.

## Alcance de datos

Las comunicaciones se consultan por `person_id` y `event_id`. Los anuncios se consultan por `event_id`. Las reservas, asistencias y certificados se consultan por acreditacion.

## WhatsApp

El inbox no envia WhatsApp por si mismo. La integracion con WhatsApp queda en contrato: los mensajes reales siguen dependiendo del modulo de comunicaciones, Safe Mode, cola y worker ya existentes.

## Seguridad

- No se muestran tokens ni secretos.
- No se muestran eventos historicos.
- No se listan comunicaciones de otros eventos.
- No se expone informacion administrativa.
