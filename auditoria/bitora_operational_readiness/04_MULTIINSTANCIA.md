# Multiinstancia

Estado runtime: **BLOCKED por daemon Docker**.

`scripts/operational_multiinstance.py` levanta PostgreSQL 16 y dos contenedores BITORA independientes. Verifica sesión cruzada, logout, cambio de rol, reinicio de una instancia, aislamiento multievento, 30 ENTRY concurrentes, replay idempotente y persistencia. Incluye ENTRY/EXIT HTTP sostenido con p50/p95/p99.

El fixture aislado y el gate de cobertura pasaron: `python verificar_operational_multiinstance.py`. La ejecución integrada generó `evidencia/operational-multiinstance.json` con error explícito `docker info timed out`; ninguna prueba runtime se marcó PASS.

