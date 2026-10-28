# Edge offline

Estado de software: **PASS local** con el cliente Edge de referencia.

Se probaron lotes de 100, 500 y 2.000 operaciones con cola SQLite/WAL, reinicio offline, reconexión, ACK parcial y desconocido, duplicados, reintentos, backoff, conflictos, orden e idempotencia. En los perfiles ejecutados: creadas = persistidas = sincronizadas, pendientes = 0, duplicadas = 0 y perdidas = 0. También se verificaron datasets de 0, 500, 3.000 y 10.000 registros con checksum, firma, revocación, expiración y clave desconocida.

Evidencia reproducible: `python -m tools.edge_client.verify_reference_client` y `python -m tools.edge_client.verify_offline_resilience`.

Limitación: esto certifica comportamiento del cliente simulado, no lectores, tablets ni equipos Edge físicos.
