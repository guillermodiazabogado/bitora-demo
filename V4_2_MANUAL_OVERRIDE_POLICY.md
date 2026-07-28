# V4.2 Manual Override Policy

Permiso requerido:

`attendance.eligibility.override`

Requisitos:

- cierre cerrado;
- evaluacion existente;
- motivo obligatorio;
- idempotency key;
- actor auditado;
- tenant validado.

El override es append-only y no elimina el resultado automatico.
