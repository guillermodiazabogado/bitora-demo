# Matriz de certificación

| Componente | Estado | Evidencia |
|---|---|---|
| Base certificada a402f8e | PASS | CI 40749664713 |
| Commit 60f5415 solo documental | PASS | Comparación de árboles |
| Wrapper persistente | PASS | Tarea programada, heartbeat y cierre `complete` |
| Instrumentación 6h | PASS | 720 muestras y consolidado final |
| Docker local | PASS LABORATORIO | Docker Engine 29.1.3 en Ubuntu WSL |
| CI del SHA evaluado | PASS | GitHub Actions 40781172427 |
| PostgreSQL 16 | PASS | Integridad, sesiones, reinicio y reconexión |
| Multiinstancia | PASS | Dos instancias, sesiones y revocación compartidas |
| Endurance 6h | PASS | 21.600,171 s; 736.461/736.461; cero fallos |
| Edge en endurance | NOT RUN | Fuera de la mezcla integrada |
| Alertas externas | BLOCKED | Sin staging/gestor externo autorizado |
| Hardware/red real | BLOCKED | Sin equipos disponibles |
| Producción | NO-GO | Sin alcance ni autorización |
