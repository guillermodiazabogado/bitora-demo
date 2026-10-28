# Readiness y balanceador

Estado automatizado local: **PASS**. Se reemplazó el uso del pool transaccional por una sonda PostgreSQL breve, con timeout configurable, caché de dos segundos y exclusión single-flight. `/health` y `/ready` devuelven una respuesta degradada estable y sanitizada; la configuración de Nginx permite retirar/reintentar ante 502/503/504 sin espera indefinida.

Evidencia: `verificar_readiness_db_failfast.py`, `verificar_production_readiness.py` y `verificar_docker_reproducible.py` aprobaron sobre los cambios locales. La prueba fail-fast exige 503 rápido, ausencia de secretos y una sola sonda concurrente.

Limitación: el corte real de PostgreSQL y red con dos contenedores y balanceador sobre el nuevo SHA está **NOT RUN**, porque el daemon Docker local no respondió. El riesgo histórico no se considera cerrado en Nivel 2 hasta ejecutar ese ensayo integrado.
