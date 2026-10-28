# Endurance 60 minutos

Estado: **PASS**.

- GitHub Actions Run: `40738606063`.
- SHA: `ba97404fad89ee166084944ad55785f1aa72ad8f`.
- Duración integrada observada: 3.630,068 segundos (nominal: 3.600).
- Operaciones HTTP: 321.488 intentadas y 321.488 exitosas; fallos técnicos: 0.
- Throughput: 89,301 operaciones/s.
- Latencia: media 11,195 ms; p50 10,884 ms; p95 13,056 ms; p99 14,016 ms.
- Muestras temporales: 121.
- Accesos persistidos: 321.489 ALLOW y 29 DENY legítimos por anti-passback.
- Todos los controles del harness: PASS, incluyendo sesiones entre instancias, replay idempotente, aislamiento multievento, reinicio/corte PostgreSQL y recuperación.
- Backup/restore aislado: PASS; RTO observado 1,844 s; RPO observado 0 s solo para dataset controlado y quiescente.
- Docker build: PASS. Dependencias e imagen: PASS, 0 vulnerabilidades altas/críticas.

Evidencia: `evidencia/run-40738606063/`.
