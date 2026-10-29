# Riesgos y limitaciones

- Laboratorio WSL comparte host con el generador; debe demostrarse que este no limita.
- 6,7 GiB de RAM disponibles para Docker/WSL.
- Red Docker loopback, no Wi-Fi/LAN de evento.
- Sin métricas detalladas de WAL/IOPS/cache hit/slow queries.
- DB_LOCK serializa transacciones dentro de cada proceso.
- Edge HTTP E2E carece de adaptador concreto en el cliente de referencia.
- Hardware real y producción quedan fuera de alcance.
- Los resultados frescos posteriores al primero registran working tree sucio solo por evidencia JSON previa; el código ejecutable permaneció en `3f3afde`.
- No se separó físicamente generador y sistema bajo prueba; 500–2.000 workers no son defendibles en este host.
- No se midió retención masiva de sesiones autenticadas.
- Datasets mayores a 3.001 acreditaciones no fueron ensayados en esta fase.
- El cambio de proyección de credenciales tiene regresiones locales, pero requiere CI remoto antes de publicación.
