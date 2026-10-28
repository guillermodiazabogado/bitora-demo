# Plan de endurance de seis horas

Criterios fijados antes del ensayo:

- Carga monotónica mínima: 21.600 segundos, excluyendo preparación y cierre.
- HTTP + PostgreSQL 16 + dos instancias + balanceador.
- Intentadas = exitosas + rechazos legítimos + errores; cero operaciones aceptadas perdidas.
- Readiness 200 y menor a 2 s durante la fase estable.
- p99 HTTP menor a 1.000 ms y p95 de última hora no superior al doble de la primera.
- Cero OOM, reinicios no programados y deadlocks.
- CPU no mayor a 85% sostenido durante cinco minutos.
- Sin crecimiento progresivo de memoria mayor a 25% desde post-warmup sin explicación.
- Conexiones menores al 80% de `max_connections`; sin locks en espera sostenidos por más de dos muestras.
- Integridad, sesiones, aislamiento, idempotencia y anti-passback en PASS.

Vouchers, leads, vehículos y Edge deben figurar NOT RUN si no se incorporan con contratos reales; no se simularán resultados.
