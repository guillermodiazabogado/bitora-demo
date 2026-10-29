# PostgreSQL e integridad

La telemetría preparada registra agregados sanitizados: tamaño de base, conexiones máximas/totales/activas/en espera, locks concedidos/en espera, commits, rollbacks, deadlocks y bytes temporales. No registra query text, DSN ni filas.

Resultado 6h: **PASS**.

- PostgreSQL 16 aislado.
- 736.462 eventos ALLOW persistidos, incluyendo el evento funcional previo a la carga.
- 29 rechazos anti-passback legítimos.
- Estado final único: OUTSIDE.
- Máximo 8 conexiones sobre 100.
- Cero deadlocks, cero locks en espera, cero rollbacks y cero bytes temporales.
- Tamaño de base: 20.986.903 a 1.258.978.327 bytes.
- Sesiones compartidas, revocación, idempotencia y aislamiento multievento: PASS.
- Reinicio, desconexión observable y recuperación: PASS.

La tasa de crecimiento observada pertenece a un dataset sintético que conserva eventos; no define todavía retención ni capacidad productiva.
