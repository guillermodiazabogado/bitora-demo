# Backlog priorizado

| ID | P | Responsable | Estado | Archivos principales | Pruebas/evidencia | Commit |
|---|---|---|---|---|---|---|
| FIN-001 | P0 | Coordinador | COMPLETADO Y VERIFICADO | `auditoria/bitora_finalizacion_enterprise/` | Inventario Git y auditoría contrastada | `ba10803` |
| FIN-002 | P0 | Backend | COMPLETADO Y VERIFICADO | `backend/security/sessions.py`, migración 049, contrato Leads, `server.py` | Auth HTTP, persistencia/restart, fuga company A→B, DB real temporal | `34e7f64` |
| FIN-003 | P0 | Seguridad/QA | COMPLETADO Y VERIFICADO localmente | Dockerfiles, restore y CI | Secret scan, Docker static gate, restore negatives, CI gate | `ba10803` |
| FIN-004 | P1 | Frontend | COMPLETADO Y VERIFICADO localmente | `enterprise-{vouchers,leads,vehicles}.*` | Node syntax, contratos UI, CSRF, scope, ausencia de mocks | `3b21c35` |
| FIN-005 | P1 | Edge/Negocio | IMPLEMENTADO, PENDIENTE DE HARDWARE | `tools/edge_client/` | 100 offline → restart → 100 ACK; checksum/HMAC y redacción | `3b21c35` |
| FIN-006 | P1 | Command Center | COMPLETADO Y VERIFICADO localmente | `frontend/app.js`, `frontend/styles.css`, servicio Command Center | stale/recovery, salud no observada, Fit/Zoom/Layers y Visual/Tabla | `1eca93e` |
| FIN-007 | P2 | DevOps/QA | IMPLEMENTADO, PENDIENTE DE PRUEBA EXTERNA | workflow CI, lock, Docker, release manifest | CI/PostgreSQL/Docker deben correr sobre commit RC | `ba10803` + `1eca93e` |
| FIN-008 | P2 | Coordinador | COMPLETADO LOCALMENTE | VERSION, release notes, SBOM y evidencia smoke | Gates locales PASS; smoke 113/113, integridad ok | `ba10803` |

Dependencias externas y criterios pendientes se detallan en `08_PENDIENTES_EXTERNOS.md`.

