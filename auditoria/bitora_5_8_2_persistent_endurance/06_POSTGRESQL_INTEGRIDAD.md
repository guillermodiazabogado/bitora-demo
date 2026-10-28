# PostgreSQL e integridad

La telemetría preparada registra agregados sanitizados: tamaño de base, conexiones máximas/totales/activas/en espera, locks concedidos/en espera, commits, rollbacks, deadlocks y bytes temporales. No registra query text, DSN ni filas.

La verificación final comparará contadores persistidos, sesiones, idempotencia, restricciones y crecimiento de base. Resultado 6h: **NOT RUN**.
