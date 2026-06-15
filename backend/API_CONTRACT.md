# Contrato API

Contrato objetivo de la API central. Los nombres actuales se mantienen cuando ya existen para no romper el sistema.

## Politica de compatibilidad V4

- Los endpoints actuales son contrato legacy-operativo.
- El frontend actual no debe romperse.
- Si en V5 se agregan rutas mas REST, las rutas actuales deben quedar como alias temporal.
- Toda regla critica debe ejecutarse en backend, nunca en frontend.

## Eventos

- `POST /api/events`: crear evento.
- `GET /api/events`: listar eventos.
- `GET /api/event?event_id=ID`: obtener evento publicado o activo.
- `POST /api/events` con `published`: publicar/despublicar evento mientras se formaliza endpoint dedicado.

## Inscripciones y acreditaciones

- `POST /api/register`: inscribir participante.
- `GET /api/portal?token=TOKEN`: portal personal del participante.
- `POST /api/portal/reserve`: reservar actividad desde portal.
- `POST /api/portal/reservations/status`: cancelar reserva desde portal.
- `POST /api/portal/preferences`: actualizar preferencias de comunicacion.
- `GET /api/accreditations`: buscar/listar acreditados.
- `POST /api/import-accreditations`: importar acreditados CSV.
- `POST /api/accreditations/update`: editar acreditado.
- `POST /api/accreditations/status`: cancelar/reactivar/acreditar manualmente.

## QR y accesos

- `GET /api/qr.svg?token=TOKEN`: generar QR.
- `POST /api/validate`: validar QR.
- `GET /api/logs`: ultimos accesos.

## Reservas y cupos

- `POST /api/reservations`: reservar actividad.
- `POST /api/reservations/status`: cancelar reserva.
- `GET /api/reservations`: listar reservas.
- `GET /api/capacity-bags`: listar bolsas de cupos.
- `POST /api/capacity-bags/move`: mover cupos entre bolsas.

## Dashboard y operacion

- `GET /api/summary`: dashboard operativo.
- `GET /api/readiness`: preparacion del evento.
- `GET /api/system-status`: estado del sistema.
- `GET /api/alerts`: alertas operativas.
- `GET /api/activity-detail`: detalle de actividad.
- `GET /api/demo-real`: ejemplos y guia de demo real para el evento activo.
- `POST /api/demo-real`: crear demo real con confirmacion `DEMO`.

## Pantalla publica

- `GET /api/public-display`: listar pantalla publica.
- `POST /api/public-display/config`: configurar modo/mensaje.
- `POST /api/public-display/item`: mostrar/ocultar actividad.

## Reportes y backups

- `GET /api/export.csv`: exportar acreditados.
- `GET /api/reservations.csv`: exportar reservas.
- `GET /api/export.json`: exportar evento completo.
- `GET /api/backup`: descargar backup.

## Auditoria, usuarios y roles

- `GET /api/audit`: listar auditoria.
- `GET /api/users`: listar usuarios operativos.
- `POST /api/users`: crear usuario/PIN.
- `POST /api/auth/login`: iniciar sesion.
- `POST /api/auth/logout`: cerrar sesion.
- `GET /api/auth/me`: sesion actual.

## Comunicaciones

- `GET /api/communications`: metricas, plantillas e historial.
- `POST /api/communications/send`: registrar envio demo segun consentimientos.

## Pendientes de formalizacion

- `POST /api/events/{id}/publish`: publicar evento.
- `POST /api/qr`: generar QR por acreditacion.
- `POST /api/audit`: auditar acciones externas o integraciones.
- `GET /api/reports/*`: reportes versionados.
- `POST /api/payments/*`: pagos y webhooks.
- `POST /api/notifications/*`: WhatsApp/email.

## Endpoints legacy a conservar mientras exista el frontend actual

- `GET /api/event`: landing publica.
- `GET /api/portal`: portal por token.
- `GET /api/qr.svg`: QR SVG local.
- `POST /api/register`: inscripcion publica y operativa.
- `POST /api/validate`: validacion QR.
- `GET /api/export.csv`, `GET /api/reservations.csv`, `GET /api/export.json`: reportes actuales.
- `GET /api/backup`: backup manual.

## Endpoints recomendados para frontend/backend separado en V5

- `GET /api/v1/events/{event_id}`
- `POST /api/v1/events`
- `POST /api/v1/events/{event_id}/publish`
- `POST /api/v1/events/{event_id}/registrations`
- `GET /api/v1/participants/{token}/portal`
- `POST /api/v1/participants/{token}/reservations`
- `DELETE /api/v1/participants/{token}/reservations/{reservation_id}`
- `POST /api/v1/access/validate`
- `GET /api/v1/events/{event_id}/dashboard`
- `GET /api/v1/events/{event_id}/public-display`
- `POST /api/v1/events/{event_id}/communications/demo-send`
- `POST /api/v1/events/{event_id}/backups`
