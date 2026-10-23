# BITORA V4 Domain Events Catalog

| Evento | Productor | Consumidores | Payload Conceptual | Idempotencia | Efectos Permitidos |
|---|---|---|---|---|---|
| ParticipantRegistered | Registro | Comunicaciones, auditoria | org, event, participant | registration id | Confirmacion segura |
| ReservationCreated | Reservas | Cupos, comunicaciones | event, activity, reservation | reservation id | Actualizar cupo |
| AccreditationCompleted | Recepcion | Acceso, auditoria | event, accreditation | accreditation id + timestamp | Habilitar QR |
| AttendanceRecorded | Asistencia | Certificados, analytics | event, activity, attendance | attendance mark key | Recalcular elegibilidad |
| AttendanceClosed | Asistencia | Certificados, reportes | event, activity/session | close id | Bloquear cambios |
| AttendanceRuleSetPublished | Asistencia | Cierres | org, event, rule version | rule version id | Habilitar cierre |
| AttendanceClosureStarted | Asistencia | Auditoria | org, event, closure | closure id | Ninguno externo |
| AttendanceClosureCompleted | Asistencia | Certificados futuros, reportes | org, event, closure, snapshot hash | closure id | Ninguno externo |
| AttendanceClosureReopened | Asistencia | Auditoria, operaciones | org, event, closure | reopening id | Ninguno externo |
| AttendanceEvaluationCreated | Asistencia | Elegibilidad | closure, participant | closure + participant | Ninguno externo |
| AttendanceEligibilityDetermined | Asistencia | Certificados futuros | closure, participant, result | evaluation id | Ninguno externo |
| AttendanceEligibilityOverridden | Asistencia | Certificados futuros, auditoria | closure, participant, override | override id | Ninguno externo |
| CertificateEligible | Certificados | Comunicaciones | event, person, rule | eligibility id | Preparar emision |
| CertificateIssued | Certificados | Portal, comunicaciones | certificate id | certificate code | Notificar si autorizado |
| CertificateTemplatePublished | Certificados | Emision | org, event, template version | template version id | Habilitar emision |
| CertificateBatchCompleted | Certificados | Auditoria | org, event, batch | batch id | Ninguno externo |
| CertificateRevoked | Certificados | Verificacion publica | issuance id | issuance id | Invalidar verificacion |
| CertificateReissued | Certificados | Verificacion publica | previous issuance, new issuance | new issuance id | Ninguno externo |
| SurveyTypeCreated | Encuestas | Auditoria | org, event, survey type | type id | Ninguno externo |
| SurveyCreated | Encuestas | Auditoria | org, event, survey | survey id | Ninguno externo |
| SurveyVersionCreated | Encuestas | Auditoria | survey, version | version id | Ninguno externo |
| SurveyPublished | Encuestas | Portal | survey version | version id | Mostrar encuesta si esta asignada |
| SurveyAssigned | Encuestas | Portal | survey, assignment | assignment id | Habilitar respuesta controlada |
| SurveyClosed | Encuestas | Portal, reportes | assignment | assignment id | Bloquear nuevas respuestas |
| SurveyCompleted | Encuestas | Analytics | survey response | response session id | Actualizar resultados internos |
| SurveyArchived | Encuestas | Portal | survey | survey id | Ocultar/bloquear respuestas |
| SpeakerAccepted | Disertantes | Agenda | speaker, event | invitation id | Cambiar estado |
| ZoneAccessDenied | Acceso | Incidencias, auditoria | zone, accreditation | scan id | Crear alerta opcional |
| IncidentCreated | Incidencias | Centro operativo | incident id | incident id | Notificar responsable |
| CommunicationScheduled | Comunicaciones | Worker | job, template | idempotency key | Encolar |

Todos los eventos incluyen tenant, actor cuando exista, timestamp, trace id y version de payload.
