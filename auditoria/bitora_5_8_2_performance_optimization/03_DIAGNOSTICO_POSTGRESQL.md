# Diagnóstico PostgreSQL

- Pool por proceso: mínimo 1, máximo 10.
- En evidencia previa, dos instancias alcanzaron 21 conexiones y cuatro aproximadamente 39–41; aumentar pools sin presupuesto puede agotar PostgreSQL.
- Cada checkout hacía `SELECT 1` y `set_config`; el pool ya posee callback de validación.
- Las búsquedas `lower(accreditations.token)` y por hash enterprise no estaban cubiertas por índices equivalentes a sus predicados.
- El esquema nuevo tiene 52 migraciones. Instalación limpia, upgrade, idempotencia, ledger y equivalencia de esquema: PASS.
- La migración 050 usa `CREATE INDEX`, no `CONCURRENTLY`; para una base grande requiere ventana de mantenimiento aunque el laboratorio haya aprobado.

Evidencia: `evidencia/postgres-migration-050.json`.
