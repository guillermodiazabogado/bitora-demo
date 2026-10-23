# BITORA V4 Participant History Architecture

## Alcance

Historial de eventos, inscripciones, reservas, asistencias, acreditaciones, certificados, encuestas, comunicaciones, incidencias, consentimientos y archivos.

## Ownership

`people` es identidad global por email, pero el historial operativo se ve por organizacion y evento. Una organizacion no puede leer historial de otra salvo politica legal y permiso explicito.

## Visibilidad

Recepcion ve datos necesarios del evento. Productor ve historial dentro de su evento. Administrador de organizacion puede ver historial organizacional. Auditor ve evidencia sanitizada.

## Privacidad

Retencion configurable por organizacion. Exportacion y eliminacion deben respetar consentimientos y obligaciones legales. Anonimizacion conserva metricas sin datos personales.

## Criterios

- Cruces de organizacion: 0.
- No sobrescritura silenciosa de datos globales.
- Cambios personales auditados.
