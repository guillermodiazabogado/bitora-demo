# Plan multiagente

La sesión dispone de subagentes reales y cuatro slots simultáneos contando al coordinador. Los seis equipos se ejecutan en oleadas.

| Equipo | Alcance | Oleada | Estado |
|---|---|---:|---|
| 1 | Endurance, perfiles y métricas | 1 | IMPLEMENTADO; endurance integrada pendiente |
| 2 | Readiness, recuperación y balanceador | 1 | IMPLEMENTADO Y PROBADO EN AISLAMIENTO |
| 3 | Edge offline y sincronización | 1 | IMPLEMENTADO Y PROBADO CON CLIENTE DE REFERENCIA |
| 4 | Observabilidad y Command Center | 2 | IMPLEMENTADO Y PROBADO LOCALMENTE |
| 5 | Infraestructura física y red | 2 | PROTOCOLO PREPARADO; CAMPO NOT RUN |
| 6 | QA, seguridad y certificación independiente | 3 | EN EJECUCIÓN |

Restricciones: worktree aislado, sin push, sin `main`, sin producción y sin datos reales. Los agentes no comparten archivos de edición en una misma oleada.
