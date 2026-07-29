# BITORA V4.10 Multitenant Report

Modelo:

- toda consulta de evento valida `organization_id`;
- comparacion permite solo eventos de la misma organizacion;
- snapshots/reportes/cierres llevan `organization_id` y `event_id`;
- restore remapea `event_id` y conserva controles.

Resultado:

- cruces permitidos: 0.
