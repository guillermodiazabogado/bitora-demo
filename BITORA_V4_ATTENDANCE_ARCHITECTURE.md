# BITORA V4 Attendance Architecture

## Diferencias Operativas

- Acreditacion: confirma identidad y habilita credencial.
- Ingreso: paso por un punto de control.
- Egreso: salida de actividad o zona.
- Presencia: estado actual inferido.
- Asistencia parcial/completa: resultado computado por regla.
- Asistencia por actividad/jornada/evento: agregaciones con criterios propios.

## Fuentes

QR, operacion manual, correccion autorizada, importacion controlada y cierre automatico supervisado.

## Estados

`no_registrado`, `acreditado`, `presente`, `ausente`, `parcial`, `completo`, `justificado`, `invalidado`, `cerrado`.

## Reglas

Cada regla pertenece a evento o actividad. Debe definir minimo requerido, modo de computo, tolerancia, obligatoriedad, cierre y relacion con certificado.

## Calculo

Porcentaje = presencia computable / duracion o actividades obligatorias. Tiempo presencial se calcula con entrada/salida validas. Elegibilidad se deriva de porcentaje, actividades obligatorias, encuesta y aprobacion manual.

## Correccion

Toda edicion requiere permiso, motivo, actor, timestamp y auditoria. Una asistencia cerrada solo se reabre con permiso especial.

## Deduplicacion

La clave natural operativa es evento, actividad, acreditacion y ventana de asistencia. Reintentos del scanner deben ser idempotentes.

## Criterios de Aceptacion

- Cruces de evento: 0.
- Correcciones sin auditoria: 0.
- Duplicados por reintento: 0.
- Visualizador no puede modificar.
- Cierre bloquea cambios salvo reapertura auditada.
