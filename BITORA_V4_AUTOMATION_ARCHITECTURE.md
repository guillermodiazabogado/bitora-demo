# BITORA V4 Automation Architecture

## Principio

Automatizaciones supervisadas, explicables y limitadas. No se permiten scripts arbitrarios ni decisiones externas no auditables.

## Estructura

Trigger, condicion, accion, aprobacion, limite, reintento, cancelacion, owner, scope, idempotency key y auditoria.

## Ejemplos Permitidos

Recordar inscripcion, recordar actividad, avisar cambio, emitir certificado, enviar encuesta, liberar cupo, mover lista de espera y alertar capacidad.

## Prohibiciones

Acciones sin ownership, ciclos, acciones externas sin rate limit, cambios masivos sin preview, envios sin Safe Mode en staging.

## Estados

`draft`, `enabled`, `paused`, `running`, `failed`, `disabled`, `expired`.

## Criterios

Cada ejecucion genera evento auditable. Reintentos son acotados. Un restore deja automatizaciones externas pausadas.
