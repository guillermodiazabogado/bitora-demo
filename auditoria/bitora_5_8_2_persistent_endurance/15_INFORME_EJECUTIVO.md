# Informe ejecutivo

La base de software sigue certificada y el commit documental no alteró ejecutables. Se implementaron localmente un runner persistente y telemetría ampliada para CPU/RAM, Docker, PostgreSQL y readiness. El wrapper aprobó pruebas repetidas de finalización y parada; la instrumentación aprobó sus smoke tests.

Se instaló Docker Engine aislado en Ubuntu WSL, se registró un runner persistente autorizado y se certificó el SHA `f9dc15e3aa8abe12c72717342fcf260ef7b81bad` con CI verde (`40781172427`). La endurance completó 21.600,171 segundos efectivos de carga HTTP sobre PostgreSQL 16 y dos instancias.

El sistema procesó 736.461/736.461 operaciones sin fallos técnicos. Las latencias fueron p50 19,876 ms, p95 32,565 ms y p99 64,835 ms. No hubo OOM, reinicios inesperados, deadlocks ni locks en espera. Sesiones compartidas, revocación, aislamiento multievento, anti-passback, idempotencia, reinicio y reconexión resultaron PASS.

La base creció hasta 1,259 GB y PostgreSQL utilizó hasta 874,80 MiB; no causó agotamiento ni degradación, aunque requiere capacidad y retención definidas para producción. Vouchers, leads, vehículos y Edge no se ejercitaron durante las seis horas.

Decisiones: software **GO**; laboratorio/endurance **PASS**; simulacro físico **NO-GO** hasta disponer y probar equipos/red/operadores reales; producción **NO-GO**.
