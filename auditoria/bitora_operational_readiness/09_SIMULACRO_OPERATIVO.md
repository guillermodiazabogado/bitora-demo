# Simulacro operativo

| Escenario | Estado | Evidencia/observación |
|---|---|---|
| A. Caída de una instancia | BLOCKED | Harness reinicia app1 y valida continuidad por app2; Docker indisponible |
| B. Reinicio PostgreSQL | NOT RUN | Requiere runtime integrado |
| C. Pérdida temporal app/DB | NOT RUN | Requiere proxy/red Docker funcional |
| D. Dos ENTRY concurrentes | BLOCKED | Harness preparado para 30 solicitudes, no ejecutado |
| E. Revocación multinstancia | BLOCKED | Sesión cruzada/rol/logout implementados, no ejecutados |
| F. Restore backup | BLOCKED | Harness preparado; `docker info` timeout |
| G. Cola Edge offline/sync | PASS unitario | Gate histórico/current fixture; falta hardware real |
| H. Servicio degradado observable | BLOCKED | Monitor preparado; runtime no iniciado |

