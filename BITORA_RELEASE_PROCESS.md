# BITORA Release Process

## Release Candidate

La Release Candidate debe registrar:

- version;
- fecha;
- branch;
- commit;
- checksum;
- migracion maxima;
- Python;
- PostgreSQL;
- sistema operativo;
- dependencias;
- estado del repositorio.

## Perfiles BSTF

- `--quick`: validacion rapida.
- `--standard`: validacion recomendada antes de deploy.
- `--release`: gate final con staging live.
- `--disaster`: fallos controlados en staging.
- `--endurance --hours 24`: operacion continua 24h.
- `--endurance --hours 72`: operacion continua 72h.
- `--cleanup`: limpia artefactos temporales de `output/supertest`.
- `--report`: muestra el ultimo resumen.

## Restricciones

No agregar funcionalidades de negocio durante certificacion. Solo se permiten correcciones, logging, pruebas, infraestructura y documentacion.
