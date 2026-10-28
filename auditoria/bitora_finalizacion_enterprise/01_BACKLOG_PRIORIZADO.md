# Backlog priorizado

| ID | Prioridad | Responsable | Estado | Dependencias | Criterio de aceptación |
|---|---|---|---|---|---|
| FIN-001 | P0 | Coordinador | COMPLETADO Y VERIFICADO | Auditoría histórica | Matriz real contrastada con HEAD |
| FIN-002 | P0 | Backend | COMPLETADO Y VERIFICADO | Contratos y persistencia | Aislamiento leads y sesiones persistentes probados |
| FIN-003 | P0 | Seguridad/QA | COMPLETADO Y VERIFICADO localmente | Configuración y CI | Pruebas negativas y gates reproducibles |
| FIN-004 | P1 | Frontend | COMPLETADO Y VERIFICADO localmente | APIs estables | Vouchers, Leads y Vehículos sin mocks |
| FIN-005 | P1 | Edge/Negocio | IMPLEMENTADO, PENDIENTE DE HARDWARE | Backend estable | Simulación offline/reconnect 100/100; hardware externo |
| FIN-006 | P1 | Command Center | COMPLETADO Y VERIFICADO localmente | Fuentes reales | Freshness, desconexión y salud no observada explícita |
| FIN-007 | P2 | DevOps/QA | IMPLEMENTADO, PENDIENTE DE PRUEBA EXTERNA | Código integrado | CI, Docker y PostgreSQL deben correr sobre RC |
| FIN-008 | P2 | Coordinador | EN DESARROLLO | Todas las oleadas | Regresión final y matriz escenarios |

Este tablero se completará con archivos, pruebas, evidencia y commits después del relevamiento paralelo.

