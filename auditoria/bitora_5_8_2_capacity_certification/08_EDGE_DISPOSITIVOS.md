# Edge y dispositivos

Simulación local ejecutada con 2, 5, 10, 25, 50 y 100 clientes, cada uno con identidad y cola SQLite/WAL independiente.

- 19.200 operaciones creadas y 19.200 ACK; pérdidas: 0.
- Reinicios y reapertura de colas: PASS.
- A 100 clientes: 10.000 operaciones drenadas en 1,4345 s (~6.971 ops/s hacia transporte en memoria).

Estado: **PASS de persistencia local simulada; BLOCKED para Edge HTTP E2E**. El transporte fue en memoria: no mide servidor, red, backoff HTTP ni hardware y su throughput no representa capacidad integral.
