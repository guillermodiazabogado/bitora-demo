# QR y accesos

Se medirán flujos HTTP completos `/api/validate` con sesión, reglas, ENTRY/EXIT, persistencia, idempotencia y anti-passback.

- Credenciales distintas: 2/4/8/12/24 dispositivos virtuales.
- Misma credencial: exactamente 1 ALLOW y N-1 ANTI_PASSBACK por ciclo.
- Objetivo: éxito válido ≥99,99% y p95 ≤500 ms.

Estado: **NOT RUN**.
