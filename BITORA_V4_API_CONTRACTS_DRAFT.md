# BITORA V4 API Contracts Draft

No se implementan endpoints en este sprint. Este documento define contratos conceptuales.

## Principios

Rutas legacy se conservan. Nuevas APIs deben declarar recurso, comando, consulta, permiso, scope, idempotencia, errores y auditoria.

## Asistencia

- Command: registrar entrada/salida.
- Command: correccion manual.
- Command: cerrar/reabrir asistencia.
- Query: asistencia por evento, actividad y participante.
- Permisos: `attendance.view`, `attendance.record`, `attendance.correct`, `attendance.close`.
- Idempotencia: clave por actividad, acreditacion, tipo de marca y ventana.

## Certificados

- Command: calcular elegibilidad.
- Command: emitir/revocar/reemitir.
- Query: certificados por evento/persona.
- Permisos: `certificates.view`, `certificates.issue`, `certificates.revoke`.

## Encuestas

- Command: crear/publicar/cerrar.
- Command portal: responder.
- Query: metricas y exportacion.
- Permisos: `surveys.manage`, `surveys.view_results`, `surveys.export`.

## Disertantes

- Command: invitar, aceptar, validar, publicar.
- Query: perfil y actividades.
- Permisos: `speakers.manage`, `speakers.self_edit`, `speakers.publish`.

## Zonas

- Command: crear zona, asignar permiso, denegar, validar acceso.
- Query: permisos por persona/zona.
- Permisos: `zones.manage`, `zones.assign`, `zones.validate`.

## Incidencias

- Command: crear, asignar, comentar, cerrar.
- Query: tablero y detalle.
- Permisos: `incidents.view`, `incidents.create`, `incidents.assign`, `incidents.close`.

## Errores

Usar errores sanitizados: permiso insuficiente, scope invalido, entidad inexistente o no visible, conflicto de estado, idempotency conflict y validacion de entrada.
