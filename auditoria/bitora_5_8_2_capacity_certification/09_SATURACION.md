# Saturación

Primera degradación por SLO:

- 2 instancias / 100 workers: inscripción p95 2.593,784 ms.
- 4 instancias / 100 workers: una de tres repeticiones con inscripción p95 2.421,011 ms y QR p95 542,073 ms.
- Matriz acumulativa: cerca de 69–77 conexiones PostgreSQL aparecieron timeouts/fallos de flujo, sin corrupción, deadlocks u OOM.

No se ejecutaron 500/1.000/2.000 workers: 100 ya incumplió y este host de 6,7 GiB no era un generador seguro para esos escalones.

En 120 segundos, 4×50 también incumplió latencia aunque mantuvo cero errores e integridad. En 2×25, inscripción cumplió; QR24 y QR12 incumplieron, mientras QR8 cumplió. El primer límite sostenido de QR está entre 8 y 12 lectores virtuales para esa configuración y mezcla.
