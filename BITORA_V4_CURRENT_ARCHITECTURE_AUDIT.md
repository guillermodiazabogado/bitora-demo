# BITORA V4 Current Architecture Audit

Fecha: 2026-07-28
Rama: develop/v4
Base RC: bitora-v1.0.0-rc.1
Runtime certificado: 3e82a6ae0deddf64fd77ba16fb4721b21902b9b2
Commit documental de partida: f87c3cd8a88151ebd6d36d0145f810e3ce7db57e

## Estado Real Relevado

BITORA es una aplicacion Python con `server.py` como fachada HTTP principal, backend modular parcial bajo `backend/services` y `backend/repositories`, frontend estatico bajo `frontend` y `static`, migraciones SQL bajo `backend/migrations`, BDF bajo `deployment` y BSTF bajo `tools/supertest` mas verificadores `verificar_*.py`.

El sistema actual ya tiene soporte operativo para eventos, personas globales, acreditaciones, actividades, reservas, cupos, QR, accesos, auditoria, usuarios, roles por evento, organizaciones, integraciones por organizacion, asignacion de integraciones por evento, jobs, worker, storage, backup, restore, disaster recovery, email, Google OAuth, WhatsApp y webhooks live.

## Estado Documentado

La Release Candidate vigente conserva gates PASSED para seguridad basica, aislamiento 20 eventos, integraciones live, backup/restore multitenant, disaster recovery y upgrade desde version anterior. `endurance_24h` permanece diferido y bloquea release estable, pero no la RC.

## Estado Supuesto Que No Debe Tomarse Como Implementado

V4 no debe asumir como producto cerrado: asistencia real completa, certificados emitibles, encuestas, disertantes autogestivos, permisos fisicos por zonas, centro operativo V4, incidencias, automatizaciones supervisadas o analytics ejecutivo. Hay piezas preparadas, por ejemplo `AttendanceService`, `activity_attendance` y `certificate_eligibility`, pero no constituyen el alcance funcional V4 completo.

## Deuda Tecnica

- `server.py` sigue concentrando ruteo, compatibilidad legacy, serializacion y reglas historicas.
- Los servicios estan parcialmente extraidos; varios dominios aun viven como funciones o bloques en la fachada.
- Existen endpoints legacy que deben conservarse mientras el frontend actual dependa de ellos.
- Algunas migraciones historicas tienen numeracion duplicada conocida, por ejemplo prefijo `007`.
- La documentacion historica menciona capacidades que deben verificarse contra codigo antes de implementarlas en V4.

## Riesgo Funcional

- Romper rutas legacy afectaria frontend, pruebas y pilotos.
- Cambios en permisos o ownership impactarian aislamiento multi-tenant.
- Cambios en jobs o comunicaciones podrian generar efectos externos si no se mantienen Safe Mode e idempotencia.
- Cambios en storage impactarian backup, restore, disaster recovery y upgrade.

## Riesgo Arquitectonico

- Agregar modulos V4 sin contratos claros aumentaria acoplamiento en `server.py`.
- Nuevas entidades sin ownership explicito podrian introducir cruces entre organizaciones o eventos.
- Automatizaciones tempranas podrian ejecutar acciones externas sin explicabilidad operativa.

## Componentes Reutilizables

- `AuditService` para trazabilidad.
- `AttendanceService` como punto de partida, sujeto a redisenio funcional.
- `BackupService` y restauracion multitenant.
- Repositorios por dominio existentes.
- Integraciones live y secretos cifrados.
- BDF/BSTF como infraestructura y certificacion.

## Decision de Diseno

V4 debe avanzar por dominios pequenos, con migraciones aditivas y flags, manteniendo compatibilidad con la RC. El primer sprint recomendado es asistencia, porque habilita certificados, encuestas obligatorias, historial y analytics.
