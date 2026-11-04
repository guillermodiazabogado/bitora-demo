# BITORA 5.8.2 — Cierre técnico de 14 días

Fecha: 2026-11-04  
Rama: `optimization/5.8.2-qr-latency-phase-6-2`  
SHA evaluado: `845a0a8dfbc0b5e74e1a3abb6c04b6f0ad508c26`  
Decisión: **NO-GO-LAB**

## Resultado ejecutivo

Se implementó una optimización focalizada en la ruta QR: la auditoría dejó de consultar el esquema de `audit_logs` en cada autorización. El cambio conserva locks, autenticación, aislamiento, anti-passback, idempotencia y persistencia. La suite dirigida de autoridad, aislamiento entre eventos, concurrencia, credenciales V5, zonas, multiinstancia y matriz HTTP terminó PASS.

La mejora fue clara en pruebas breves: con 24 lectores durante 180 segundos se observaron 21.532/21.532 autorizaciones, p95 377,086 ms, p99 406,212 ms, 119,429/s, cero errores y cero deadlocks. Sin embargo, la certificación sostenida no fue repetible:

| Prueba | Duración | Autorizaciones | Throughput | p95 | p99 | Integridad |
|---|---:|---:|---:|---:|---:|---|
| QR 24 R1 | 600,308 s | 52.573/52.573 | 87,577/s | 497,053 ms | 1.087,406 ms | PASS |
| QR 24 R2 | 600,316 s | 44.802/44.802 | 74,631/s | 608,861 ms | 1.411,363 ms | PASS |
| QR 24 R3 | — | — | — | — | — | NOT_RUN |

R2 incumplió el SLO oficial p95 <=500 ms. No hubo errores técnicos, timeouts, deadlocks, duplicados, OOM ni reinicios inesperados; la reconciliación y la semántica de las 44.802 autorizaciones fueron correctas. El supervisor detuvo la campaña antes de R3 y de anti-passback, como exigían los gates.

## Cambios y garantías

- Optimización conservada: eliminación de introspección SQL redundante por auditoría.
- Nuevas regresiones: contrato de esquema de auditoría y matriz HTTP para credencial válida, replay, desconocida, inactiva y revocada.
- Runner autónomo: Task Scheduler, lock exclusivo, checkpoint atómico, SHA limpio, estados STARTING/READY/RUNNING/STOPPING/FINISHED y detención ante FAIL.
- Un intento anterior quedó INCOMPLETE por un falso positivo del supervisor durante la recuperación controlada; no se reutilizó. La corrección fue validada por smoke antes de iniciar la campaña final.
- Inscripciones certificadas previamente: se preservan R1/R2/R3, 102.199 confirmadas, sin duplicados, timeouts ni deadlocks. La optimización no modificó ese flujo.

## Decisiones

- QR válido sostenido: **FAIL** por falta de repetibilidad del p95.
- Anti-passback 16 y 24 lectores: **NOT_RUN**, bloqueado por el gate QR.
- Integridad y seguridad en las corridas ejecutadas: **PASS**.
- GO de laboratorio: **NO-GO-LAB**.
- Staging: **BLOCKED** hasta lograr tres PASS QR y completar anti-passback.
- Producción: **NO-GO**; además continúan pendientes red, lectores y Edge físicos, capacidad productiva y simulacro presencial.

## Próxima acción imprescindible

No repetir la misma campaña. El siguiente ciclo debe partir de una hipótesis nueva respaldada por profiling de la variabilidad sostenida observada entre R1 y R2, con énfasis en pool PostgreSQL, colas por proceso y picos p99. Cualquier cambio deberá conservar las regresiones y volver a congelar un SHA limpio.

No se realizó push, merge, cambio en `main` ni despliegue.
