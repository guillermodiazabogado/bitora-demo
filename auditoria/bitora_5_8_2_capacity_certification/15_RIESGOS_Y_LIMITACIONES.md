# Riesgos y limitaciones

- Laboratorio WSL comparte host con el generador; debe demostrarse que este no limita.
- 6,7 GiB de RAM disponibles para Docker/WSL.
- Red Docker loopback, no Wi-Fi/LAN de evento.
- Sin métricas detalladas de WAL/IOPS/cache hit/slow queries.
- DB_LOCK serializa transacciones dentro de cada proceso.
- Edge HTTP E2E carece de adaptador concreto en el cliente de referencia.
- Hardware real y producción quedan fuera de alcance.
