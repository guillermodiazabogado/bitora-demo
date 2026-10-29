# PostgreSQL

- PostgreSQL 16 aislado por ejecución.
- Máximos en puntos certificados: 11 conexiones (1 instancia), 21 (2) y 40–41 (4), sobre límite 100.
- Deadlocks: 0. Locks pendientes sostenidos: 0. OOM: 0. Reinicios inesperados: 0.
- Integridad: sin tokens/emails duplicados y sin pérdida de altas aceptadas.
- La matriz acumulativa llegó a 69–77 conexiones y degradó celdas posteriores; esas cifras no certifican throughput.

Primer cuello de botella observado: serialización por proceso en rutas críticas (`DB_LOCK`) y presión de pools/conexiones al crecer instancias y workers. No se midieron WAL, IOPS ni `pg_stat_statements`.
