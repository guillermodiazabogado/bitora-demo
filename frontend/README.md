# Frontend

Aplicacion web operativa y publica de la plataforma.

Incluye:

- Dashboard operativo.
- Recepcion.
- Escaner QR.
- Pantalla publica.
- Portal participante.
- Landing publica.

Regla de arquitectura: el frontend consume API. Las reglas criticas no deben duplicarse aca; validacion de QR, cupos, reservas, auditoria y permisos viven en backend.

La pantalla publica debe permanecer sin datos sensibles: no mostrar DNI, email, telefono, operadores, auditoria, pagos, capacidad fisica total ni bolsas internas privadas.
