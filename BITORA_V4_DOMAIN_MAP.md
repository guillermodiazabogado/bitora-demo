# BITORA V4 Domain Map

| Dominio | Proposito | Entidades | Ownership | Interfaces | Riesgos |
|---|---|---|---|---|---|
| Identidad y acceso | Autenticacion, sesiones y permisos | users, roles, permissions | Plataforma/org/evento | Login, permisos, sesiones | Elevacion de privilegios |
| Organizaciones | Tenant y configuracion | organizations, organization_users | Organizacion | Admin org | Cruces tenant |
| Eventos | Unidad operativa | events, event_settings | Organizacion/evento | Configuracion, dashboard | Config ambigua |
| Actividades | Agenda y cupos | activities, spaces | Evento | Agenda, reservas | Solapamientos |
| Participantes | Identidad operativa | people, accreditations | Persona global/evento | Registro, recepcion | Duplicados |
| Registro | Inscripcion | registrations, preferences | Evento/participante | Landing, portal | Consentimiento |
| Reservas y cupos | Capacidad | reservations, capacity_bags | Evento/actividad | Portal, recepcion | Sobreventa |
| Acreditacion | Check-in | accreditations, QR | Evento/persona | Recepcion | Correcciones indebidas |
| Control acceso | Ingresos | access_logs | Evento/zona | Scanner | Reingreso indebido |
| Asistencia real | Presencia computable | activity_attendance | Evento/actividad | Scanner/manual | Calculo incorrecto |
| Certificados | Elegibilidad y emision | certificate_eligibility, certificates | Evento/persona | Portal, admin | Emision indebida |
| Encuestas | Feedback | surveys, responses | Evento/actividad | Portal | Privacidad |
| Disertantes | Speaker ops | speakers, materials | Organizacion/evento | Portal speaker | Datos incompletos |
| Comunicaciones | Mensajeria | templates, jobs, logs | Org/evento | Admin, worker | Envios incorrectos |
| Automatizaciones | Acciones supervisadas | rules, executions | Org/evento | Scheduler/worker | Ciclos/duplicados |
| Auditoria | Evidencia | audit_logs | Plataforma/org/evento | Consultas | Datos sensibles |
| Exportaciones | Salidas controladas | export_jobs | Org/evento | CSV/JSON/PDF | Fuga de datos |
| Reportes | Lecturas operativas | report_snapshots | Org/evento | Dashboard | Metricas inconsistentes |
| Analytics | KPIs | metric_snapshots | Org/evento | Ejecutivo | Interpretacion erronea |
| Storage | Archivos | storage_objects | Org/evento | Upload/download | Traversal |
| Integraciones | Proveedores externos | organization_integrations | Organizacion | Admin/worker | Secretos |
| Configuracion | Parametros | settings, flags | Plataforma/org/evento | Admin | Flags eternos |
| Operacion | Estado en vivo | incidents, room_status | Evento | Centro operativo | Ruido |
| Monitoreo | Salud tecnica | health, logs | Plataforma | BDF/BSTF | Falsos positivos |

## Eventos de Dominio

Cada dominio debe emitir eventos conceptuales auditables con tenant, actor, idempotency key y payload minimo. Los consumidores no deben resolver tenant por parametros no confiables.

## Dependencias Principales

Asistencia depende de eventos, actividades, participantes, acreditaciones y QR. Certificados dependen de asistencia y encuestas. Analytics depende de snapshots de asistencia, reservas, accesos, comunicaciones y encuestas.
