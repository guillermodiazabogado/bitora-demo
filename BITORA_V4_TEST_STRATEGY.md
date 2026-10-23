# BITORA V4 Test Strategy

## Niveles

Unitarios, integracion, contratos, permisos, multitenant, jobs, UI, end-to-end, regresion, seguridad, carga, backup, restore y upgrade.

## Minimos por Modulo MVP

| Modulo | Pruebas Minimas |
|---|---|
| Asistencia | registro, correccion, cierre, reingreso, evento ajeno, visualizador 403 |
| Certificados | elegibilidad, emision, revocacion, storage, backup/restore |
| Encuestas | versionado, anonima, identificada, cierre, exportacion |
| Disertantes | invitacion, permisos, storage, publicacion |
| Zonas | permiso, denegacion, vigencia, QR ajeno, offline snapshot |
| Historial | visibilidad por organizacion, privacidad, exportacion |
| Autocomplete | conflicto, consentimiento, no cruce |
| Incidencias | estados, comentarios, asignacion, auditoria |
| Comunicaciones | Safe Mode, idempotencia, integracion ajena |

## Regresion

Cada sprint V4 debe ejecutar seguridad, aislamiento, tests del modulo, contratos de API afectados, backup/restore si cambia datos, upgrade si hay migracion y live tests si cambia integracion.

## Evidencia

Toda prueba relevante produce reporte con commit, run id, dataset, estado, riesgos y secretos expuestos = 0.
