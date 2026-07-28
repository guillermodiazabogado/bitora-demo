# BITORA V4 Reporting Analytics Architecture

## Tipos de Reporte

Operativo, ejecutivo, auditoria, participante, actividad, asistencia, capacidad, comunicaciones, certificados y encuestas.

## KPIs Iniciales

Inscriptos, acreditados, presentes, ausentes, conversion, ocupacion, no-show, permanencia, actividad, satisfaccion, certificados y comunicaciones.

## Fuente y Consistencia

Los reportes operativos pueden leer estado actual. Los reportes ejecutivos deben usar snapshots con timestamp, filtros y version de calculo.

## Permisos

Cada reporte define datos visibles y exportables. Datos personales completos requieren permiso especifico.

## Exportacion

CSV/JSON/PDF como jobs auditados, con scope, actor y motivo.

## Criterios

- Filtros por organizacion/evento obligatorios.
- Calculo reproducible.
- Exportaciones quedan auditadas.
