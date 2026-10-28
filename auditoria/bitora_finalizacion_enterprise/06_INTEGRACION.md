# Registro de integración

- Baseline congelado: `30051df`.
- No se crearán commits hasta terminar una unidad coherente y revisar el diff selectivo.
- Se preservarán todos los cambios locales anteriores a la operación.
- Cada integración significativa debe repetir compilación, gates críticos y `git diff --check`.

## Oleadas integradas

1. Fundaciones: aislamiento Lead Retrieval, consentimiento company-scoped, Docker reproducible.
2. Operación: cliente Edge durable y UIs Vouchers/Leads/Vehículos.
3. Confiabilidad: sesiones persistentes, Command Center stale/freshness y restore seguro.
4. RC: versión `5.8.2-rc.1`, migración 049, release notes y gates CI.

Regresión local integrada: PASS. Certificación PostgreSQL/Docker externa: pendiente.

