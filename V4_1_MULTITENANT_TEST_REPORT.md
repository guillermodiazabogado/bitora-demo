# V4.1 Multitenant Test Report

## Dataset

2 organizaciones, 4 eventos, 2 actividades por evento y participantes por evento.

## Casos

- Actividad de otro evento rechazada.
- Participante se valida mediante acreditacion del evento.
- Listado y detalle requieren organizacion derivada del evento.
- Idempotency key scoped por organizacion.

## Resultado

Cross-organization reads: 0
Cross-organization writes: 0
Cross-event writes: 0
Cross-activity references: 0
