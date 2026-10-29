# Resultado endurance de seis horas

Estado: **PASS**.

- SHA evaluado: `f9dc15e3aa8abe12c72717342fcf260ef7b81bad`.
- CI previo: GitHub Actions `40781172427`, PASS sobre ese SHA.
- Inicio de carga: 2026-10-28 19:39:30 ART.
- Fin: 2026-10-29 01:40:39 ART.
- Carga monotónica efectiva: 21.600,171 s; ejecución integral: 21.693,584 s.
- Arquitectura: HTTP real, PostgreSQL 16 y dos instancias de BITORA.
- Operaciones: 736.461 intentadas y 736.461 exitosas; cero fallos técnicos.
- Persistencia: 736.462 eventos ALLOW (incluye el evento funcional previo) y 29 DENY legítimos por anti-passback.
- Latencias: p50 19,876 ms; p95 32,565 ms; p99 64,835 ms.
- Throughput medio: 34,095 operaciones/s.
- `/ready`: 1.440/1.440 respuestas HTTP 200; máximo observado 118,979 ms.
- PostgreSQL: cero deadlocks, cero locks en espera, máximo 8/100 conexiones.
- Contenedores: cero OOM y cero reinicios inesperados.

Pasaron los controles de sesiones entre instancias, logout, revocación por cambio de rol, aislamiento multievento, concurrencia anti-passback, replay idempotente, reinicio de PostgreSQL, desconexión/reconexión e integridad final.

Evidencia: `evidencia/endurance-6h-f9dc15e-r2/result.json`, `result.harness.json` y `run-metadata.json`.

Limitación: vouchers, Lead Retrieval, vehículos y Edge no formaron parte de esta mezcla prolongada y permanecen NOT RUN en este ensayo.
