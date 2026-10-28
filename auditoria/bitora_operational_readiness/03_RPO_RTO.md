# RPO y RTO

RPO observado: **NOT MEASURED**. RTO observado: **NOT MEASURED**. La ejecución fue bloqueada antes de crear PostgreSQL.

El harness calculará RTO como tiempo real de `pg_restore`. Solo reportará RPO observado `0` para un dataset controlado y detenido durante el dump; esto no equivale a RPO cero productivo, replicación ni objetivo acordado.

