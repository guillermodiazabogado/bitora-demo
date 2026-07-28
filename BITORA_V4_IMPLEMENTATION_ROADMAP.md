# BITORA V4 Implementation Roadmap

## Sprint V4.1 - Attendance Domain Foundation

Objetivo: base de asistencia real.
Alcance: modelo, permisos, endpoints, UI minima, auditoria y pruebas multitenant.
Exclusiones: certificados PDF y automatizaciones.
Gates: seguridad, aislamiento, backup/restore, upgrade.
Estado: IMPLEMENTED / TESTED / PENDING CERTIFICATION.

## Sprint V4.2 - Attendance Closing and Eligibility

Objetivo: cierres, reaperturas y elegibilidad.
Dependencia: V4.1.
Gates: seguridad, auditoria, jobs si aplica.
Estado: IMPLEMENTED / TESTED / PENDING REVIEW.

## Sprint V4.3 - Certificates

Objetivo: certificados verificables y revocables.
Dependencia: V4.2, storage.
Gates: storage, backup, restore, comunicaciones si hay envio.
Estado: IMPLEMENTED / TESTED / PENDING REVIEW.

## Sprint V4.4 - Surveys

Objetivo: encuestas versionadas.
Dependencia: participantes, portal.
Gates: privacidad, exportaciones, multitenant.

## Sprint V4.5 - Speakers

Objetivo: disertantes autogestivos.
Dependencia: actividades, storage.
Gates: RBAC, storage, multitenant.

## Sprint V4.6 - Zone Permissions

Objetivo: permisos fisicos/logicos por zona.
Dependencia: QR, accesos.
Gates: seguridad, aislamiento, carga.

## Sprint V4.7 - History and Autocomplete

Objetivo: historial participante y reutilizacion segura.
Dependencia: people, consentimientos.
Gates: privacidad, multitenant.

## Sprint V4.8 - Operations Center

Objetivo: panel operativo.
Dependencia: asistencia, incidencias, jobs.
Gates: UI, permisos, performance.

## Sprint V4.9 - Communications and Supervised Automation

Objetivo: evolucion de comunicaciones y automatizaciones controladas.
Dependencia: jobs, integraciones certificadas.
Gates: Email, WhatsApp, Safe Mode, DR.

## Sprint V4.10 - Analytics and Closing

Objetivo: KPIs, reportes finales y cierre operativo.
Dependencia: snapshots.
Gates: reportes, exportaciones, performance.
