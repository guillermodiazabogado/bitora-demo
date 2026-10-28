# Seguridad y regresiones

Estado: **PASS LOCAL PARCIAL** con revisión independiente de QA sobre `3fa5c7da55677b32d9babc2aeb49a3e72bf66e7d`.

Pruebas aprobadas localmente: readiness fail-fast, production readiness, Dockerfile reproducible, perfiles de endurance, cliente Edge de referencia, resiliencia offline Edge, fundamentos V5.2, Edge V5.8, observabilidad operacional, runner integrado estructural, seguridad operacional, sesiones/revocación, autenticación/CSRF/cookies/rate limiting, aislamiento de dispositivos y concurrencia crítica (1 autorización y 99 rechazos correctos).

El secret scan independiente del rango `2b703a1..HEAD` no encontró credenciales reales. El hallazgo de CPU del colector fue corregido: ahora usa delta de proceso/intervalo normalizado por CPU lógica y la regresión aprobó.

La suite remota operacional, Docker/PostgreSQL real, dependency audit y escaneo de imagen aprobaron en los runs `40735837313` y `40738606063` para `ba97404fad89ee166084944ad55785f1aa72ad8f`. La evidencia del SHA anterior no se utilizó como sustituto.

El CI completo final aprobó en el Run `40749664713` para `a402f8e48db842454738561374e18efa7454bf8e`: compilación, smoke de endurance, regresiones críticas, secret scan, SBOM CycloneDX, PostgreSQL, Docker build y runtime/healthcheck. Evidencia: `evidencia/run-40749664713/`.
