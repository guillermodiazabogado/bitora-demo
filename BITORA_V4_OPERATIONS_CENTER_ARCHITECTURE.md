# BITORA V4 Operations Center Architecture

## Proposito

Panel vivo para operar evento, jornada, sala y actividad sin depender de reportes dispersos.

## Vistas

Organizacion, evento, jornada, sala, actividad, recepcion y acceso.

## Metricas

Participantes, acreditaciones, ingresos, presentes, ausentes, ocupacion, cupos, incidencias, jobs, comunicaciones, integraciones y estado de servicios.

## Estados y Alertas

Capacidad critica, cola atascada, integracion degradada, sala sin operador, actividad por iniciar, asistencia sin cierre, incidentes abiertos y storage/backup no disponible.

## Acciones Rapidas

Pausar comunicaciones, abrir incidencia, exportar corte, cerrar asistencia, reasignar operador y revisar job. Cada accion requiere permiso y auditoria.

## Criterios

El panel no debe reemplazar autorizacion backend. Datos se filtran por organizacion/evento. Actualizacion en vivo debe ser consistente y tolerar reconexion.
