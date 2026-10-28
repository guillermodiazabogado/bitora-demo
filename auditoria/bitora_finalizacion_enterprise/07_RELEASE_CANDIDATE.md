# Release candidate

Identificador: `5.8.2-rc.1`.

Estado: código integrado localmente; certificación externa pendiente.

- Dependencias: `requirements.lock`.
- Base objetivo: PostgreSQL 16, última migración 049.
- Contenedor: no-root UID 10001, readiness `/ready`.
- SBOM: generador incluido; regeneración pendiente sobre commit RC.
- Notas: `BITORA_5.8.2-rc.1_RELEASE_NOTES.md`.
- Rollback: volver a imagen/commit anterior; migración 049 es aditiva.

Crear esta RC no constituye aprobación productiva.

