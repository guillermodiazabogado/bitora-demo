# BITORA V4 Domain Events Catalog

| Evento | Productor | Consumidores | Payload Conceptual | Idempotencia | Efectos Permitidos |
|---|---|---|---|---|---|
| ParticipantRegistered | Registro | Comunicaciones, auditoria | org, event, participant | registration id | Confirmacion segura |
| ReservationCreated | Reservas | Cupos, comunicaciones | event, activity, reservation | reservation id | Actualizar cupo |
| AccreditationCompleted | Recepcion | Acceso, auditoria | event, accreditation | accreditation id + timestamp | Habilitar QR |
| AttendanceRecorded | Asistencia | Certificados, analytics | event, activity, attendance | attendance mark key | Recalcular elegibilidad |
| AttendanceClosed | Asistencia | Certificados, reportes | event, activity/session | close id | Bloquear cambios |
| CertificateEligible | Certificados | Comunicaciones | event, person, rule | eligibility id | Preparar emision |
| CertificateIssued | Certificados | Portal, comunicaciones | certificate id | certificate code | Notificar si autorizado |
| SurveyPublished | Encuestas | Portal, comunicaciones | survey version | survey version | Mostrar encuesta |
| SurveyCompleted | Encuestas | Certificados, analytics | survey response | response id | Recalcular condicion |
| SpeakerAccepted | Disertantes | Agenda | speaker, event | invitation id | Cambiar estado |
| ZoneAccessDenied | Acceso | Incidencias, auditoria | zone, accreditation | scan id | Crear alerta opcional |
| IncidentCreated | Incidencias | Centro operativo | incident id | incident id | Notificar responsable |
| CommunicationScheduled | Comunicaciones | Worker | job, template | idempotency key | Encolar |

Todos los eventos incluyen tenant, actor cuando exista, timestamp, trace id y version de payload.
