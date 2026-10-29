# BITORA 5.8.2 — Preflight de optimización

- Fecha: 2026-10-29.
- Rama: `optimization/5.8.2-concurrency-postgresql-qr`.
- Base: `f1098e2c5d1c4604f505ec7eb82e752efcfcd110`.
- Referencias verificadas: `3f3afde`, `6ba0aeb` y `8be0091` existen en el repositorio.
- Entorno: Docker Desktop mediante Ubuntu WSL, PostgreSQL 16 aislado y datos sintéticos.
- Producción, `main`, secretos y datos reales: no utilizados.
- Subagentes: tres agentes reales de concurrencia, PostgreSQL y QR. El primer intento fue bloqueado por cuota; el segundo intento completó los diagnósticos sin editar archivos.

## Estado inicial reproducido

En `f1098e2`, dos instancias, 25 workers y 12 lectores virtuales durante 120 s:

- 42,705 inscripciones E2E/s; p95 790,696 ms.
- 103,588 decisiones QR/s; p95 135,589 ms.
- cero errores técnicos, cero deadlocks e integridad PASS.

Evidencia: `evidencia/baseline-i2-w25-qr12.json`.
