# V4.2 Security Report

Validaciones:

- feature flag requerido;
- dependencia con V4.1;
- permisos backend por accion;
- tenant derivado del evento;
- actividad dentro del evento;
- regla publicada obligatoria para cerrar;
- schema cerrado de reglas;
- sin `eval`, `exec` ni codigo dinamico;
- idempotencia en operaciones sensibles;
- snapshot hash estable;
- secretos expuestos: 0.

Nuevos hallazgos HIGH: 0

Hallazgo heredado: documentado en `INHERITED_SECURITY_FINDING_UPGRADE_SCRIPT.md`.
