# BITORA V4.5 - Backup/Restore Report

Resultado: PASSED.

El backup de evento incluye perfiles asignados al evento, datos privados, versiones, asignaciones, documentos y tokens.

Restore como nuevo evento:

- remapea `event_id`;
- remapea actividades;
- remapea perfiles y versiones;
- remapea storage de documentos;
- regenera hashes de tokens;
- marca tokens restaurados como `RESTORED_INACTIVE`.
