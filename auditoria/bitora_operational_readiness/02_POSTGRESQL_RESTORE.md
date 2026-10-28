# PostgreSQL backup y restore

Estado: **BLOCKED por daemon Docker local no disponible**.

Implementado: `scripts/operational_postgres_restore.py`. Crea PostgreSQL 16 y una imagen BITORA efímeros, aplica migraciones, carga un marcador controlado, ejecuta `pg_dump -Fc`, calcula SHA-256, restaura con `pg_restore`, compara conteos y restricciones y limpia solo recursos con nombre aleatorio.

Verificación estática: `python verificar_operational_postgres_restore.py` — PASS.

Ejecución real intentada sobre `8985301`: `docker info` agotó 30 segundos. Evidencia: `evidencia/postgres-restore.json`. No hubo acceso a bases externas ni datos reales.

