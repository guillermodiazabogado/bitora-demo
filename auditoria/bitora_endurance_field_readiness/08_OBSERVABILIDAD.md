# Observabilidad

Estado local: **PASS** para generación y ciclo de alertas del tablero mínimo.

`scripts/operational_observability.py` produce JSON y HTML sin dependencias adicionales. Registra CPU, RAM, API, latencia, PostgreSQL, conexiones, cola Edge, dispositivos y freshness. Cada señal exige procedencia `observed`, `simulated` o `unavailable`.

Se verificó el ciclo activación/resolución de API caída, DB caída, tasa de error, latencia, cola acumulada, dispositivo desconectado y snapshot desactualizado mediante `verificar_operational_observability.py`.

Limitación: las alertas locales simuladas no equivalen a monitoreo de staging o producción. Las fuentes sin endpoint o credenciales permanecen explícitamente `unavailable`.
