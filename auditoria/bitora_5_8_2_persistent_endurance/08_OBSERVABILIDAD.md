# Observabilidad

Se añadieron checkpoints atómicos, tendencias, readiness periódico y métricas Docker/PostgreSQL. El runner persistente conserva heartbeat y logs aunque se cierre la conversación.

Resultado en laboratorio 6h: **PASS** para telemetría y checkpoints.

- 720 muestras de infraestructura y 1.440 chequeos de readiness.
- Heartbeat persistente cada 30 segundos.
- Estado, PID, tiempo monotónico y salida final preservados tras finalizar.
- Identificación de OOM, reinicios, CPU, RAM, I/O, conexiones, locks y crecimiento de base.
- `/ready` respondió 200 en todas las muestras, con máximo 118,979 ms.

No se validó un gestor externo de alertas ni notificaciones a operadores. Esa parte continúa BLOCKED para staging/campo.
