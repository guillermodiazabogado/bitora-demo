# Edge y dispositivos

El cliente de referencia conserva colas SQLite independientes y backoff, pero hoy expone una interfaz abstracta `EdgeTransport`; no existe adaptador HTTP concreto integrado con `/heartbeat` y `/sync`.

- Simulación local multi-cliente: PENDIENTE.
- Edge HTTP E2E: BLOCKED hasta implementar y verificar un transporte real.
- Dispositivos físicos: NOT RUN.

Una simulación no certificará hardware.
