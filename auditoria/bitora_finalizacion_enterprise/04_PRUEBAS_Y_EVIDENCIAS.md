# Pruebas y evidencias

| Fecha | Commit | Prueba | Resultado | Evidencia/limitación |
|---|---|---|---|---|
| 2026-10-27 | `30051df` | Compilación Python | PASS | Runtime Codex Python 3.12.14 |
| 2026-10-27 | `30051df` | `verificar_production_readiness.py` | PASS | Salida local: readiness, health, HTTPS/config, storage y documentos |
| 2026-10-27 | `30051df` | Docker local | BLOQUEADO | Docker Desktop no está activo |
| 2026-10-27 | working tree `5.8.2-rc.1` | 33 gates locales integrados | PASS | `ALL_LOCAL_RC_GATES_PASS` |
| 2026-10-27 | working tree `5.8.2-rc.1` | Edge offline/restart/reconnect | PASS | 100 operaciones, 100 ACK, cero pérdidas |
| 2026-10-27 | working tree `5.8.2-rc.1` | Sesiones persistentes + E2E auth HTTP | PASS | restart, expiry, revoke, CSRF y cookie segura |
| 2026-10-27 | working tree `5.8.2-rc.1` | Leads/Vehículos DB real temporal | PASS | aislamiento, consentimiento, idempotencia, anti-passback |

La evidencia histórica se usa como baseline, no como sustituto de pruebas sobre la RC.

