# Métricas de rendimiento

La instrumentación preparada toma cada 30 segundos:

- CPU, memoria, PIDs, red, I/O, OOM y reinicios de app-a, app-b y PostgreSQL.
- Estado y latencia de `/ready` por instancia.
- Operaciones, fallos totales y detalle limitado a veinte fallos.
- Latencias, throughput y tendencias primera/última hora.

Resultados de seis horas: **PASS**.

| Métrica | Resultado |
|---|---:|
| Operaciones | 736.461 |
| Fallos técnicos | 0 |
| Throughput medio | 34,095 op/s |
| Latencia media | 24,123 ms |
| p50 / p95 / p99 | 19,876 / 32,565 / 64,835 ms |
| Muestras de infraestructura | 720 |
| CPU máxima app-a / app-b | 21,11% / 21,88% |
| CPU máxima PostgreSQL | 44,74% |
| Memoria app-a, inicio/final/máxima | 67,77 / 69,61 / 82,82 MiB |
| Memoria app-b, inicio/final/máxima | 68,53 / 70,47 / 83,97 MiB |
| Readiness máximo | 118,979 ms |

No se observó agotamiento de CPU, memoria o conexiones. La memoria de las aplicaciones permaneció estable después del warm-up. PostgreSQL creció de 27,36 a 874,80 MiB mientras la base pasó de 20,99 MiB a 1.258,98 MB. La revisión independiente calculó correlación 0,9977 entre memoria PostgreSQL y crecimiento de base/operaciones, sin aceleración, OOM ni degradación; es fuertemente compatible con caché/buffers, no con una fuga demostrada. Como no alcanzó un plateau, una prueba de 12 horas deberá separar RSS/caché y medir WAL, disco e I/O con límites explícitos. No se almacenaron histogramas horarios de latencia HTTP; la ausencia de degradación se sustenta en readiness, recursos y resultado global, no en una comparación p95 primera/última hora.
