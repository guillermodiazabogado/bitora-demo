# V4.3 Backup Restore Report

Backup por evento incluye:

- tipos;
- plantillas;
- versiones;
- secuencias;
- batches;
- emisiones;
- documentos;
- token hashes;
- revocaciones;
- reemisiones.

Restore remapea:

- evento;
- participantes/personas;
- cierres/evaluaciones/decisiones;
- tipos/plantillas/versiones;
- batches/emisiones/documentos;
- rutas de storage.

Para restore como nuevo evento se regeneran valores operativos que pueden colisionar: idempotency keys y token hashes.
