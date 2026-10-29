# Metodología

Se usarán recursos Docker únicos y eliminables, PostgreSQL 16, imagen construida desde el SHA evaluado y generador externo al proceso de aplicación. Cada escalón incluye warm-up, medición, descenso de carga, recuperación e integridad.

- Inscripción: modelo cerrado por usuarios virtuales; flujo completo `GET event → POST register → GET portal → GET QR`.
- QR: dispositivos virtuales con sesión propia; credenciales distintas y contención sobre la misma credencial.
- Escalabilidad: comparación 1/2/4 instancias con misma base, imagen y host.
- Capacidad certificada: mayor escalón repetible que cumple SLO e integridad.
- Saturación: primer escalón que incumple SLO o umbrales de recursos; no se redefine después de observar resultados.

SLO previos:

- Inscripción válida: éxito ≥99,9%, p95 del flujo ≤2.000 ms.
- QR: respuesta válida ≥99,99%, p95 ≤500 ms.
- PostgreSQL: menos de 80/100 conexiones, cero deadlocks y cero locks pendientes sostenidos.
- Infraestructura: sin OOM/reinicios; CPU del host/servicio no mayor a 85% sostenido cinco minutos.
- Integridad: cero operaciones aceptadas perdidas, duplicadas indebidamente o fuera de evento.

Escalones se detienen ante fallo crítico, agotamiento del host o dos incumplimientos consecutivos.
