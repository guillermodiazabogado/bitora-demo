# BITORA — Plan de acción priorizado y estado de ejecución

Fecha de actualización: 2026-10-26. Esta tabla describe cambios presentes en el
working tree; no implica despliegue ni certificación productiva.

| Ítem | Estado actual | Evidencia reproducible | Pendiente externo |
|---|---|---|---|
| P0-01 Autoridad de accesos | Implementado y validado localmente | `verificar_p0_access_authority.py`, `verificar_p0_access_activation.py` | Certificación PostgreSQL real |
| P0-02 Aislamiento multievento | Implementado y validado | `verificar_p0_access_event_scope.py`, matriz 20 eventos/1000 participantes | Ninguno para alcance local |
| P0-03 Contratos enterprise | Implementados en dominio y HTTP | verificadores V5.4/V5.5/V5.6 y Edge | E2E HTTP en host que permita sockets; clientes operativos dedicados |
| P0-04 Certificación PostgreSQL | Harness y gate CI implementados | `scripts/certify_postgres.py` | Ejecutar contra PostgreSQL 16; Docker local no disponible |
| P0-05 Runtime reproducible | Implementado | `requirements.lock`, CI, SBOM, manifest | Ejecutar CI remota |
| P1 Seguridad web/dispositivos | Implementado y validado directamente | Argon2id, migración legacy, CSRF, cookie segura, rate limit persistente, dispositivos `ACTIVE` | Repetir E2E HTTP fuera de este sandbox |
| P1 Concurrencia | Implementado y validado localmente | 30 ENTRY: 1 ALLOW/29 anti-passback; advisory lock PostgreSQL | Prueba multiinstancia con PostgreSQL real |
| P1 Endurance | Harness real y workflow manual implementados | smoke local 3 s, 16 operaciones, integridad `ok`, cero fallos | Ejecutar y conservar corrida formal de 24 h |
| P2 Versionado/SBOM | Implementado | `VERSION`, `release-manifest.json`, SBOM CycloneDX | Publicar artefactos mediante CI |

Los estados “implementado” no convierten por sí solos al producto en apto para
producción. Los tres gates externos —PostgreSQL real, E2E HTTP completo y endurance
24 h— deben terminar satisfactoriamente sobre el mismo commit congelado.

## P0 — Bloqueantes críticos

### P0-01 — Autoridad única de accesos

- Objetivo: hacer del Access State Engine la fuente transaccional de ENTRY/EXIT.
- Problema: V4 decide y V5.1 observa después.
- Dependencias: QR, ocupación, dispositivos y Command Center.
- Complejidad: alta. Riesgo de implementación: alto.
- Aceptación: anti-passback, cooldown, idempotencia y ocupación pasan concurrencia; no existe concesión legacy previa.
- Pruebas: unidad, integración API, replay, concurrencia y rollback.
- Resultado: cerrado en código; V5 decide antes de persistir y falla cerrado.

### P0-02 — Aislamiento multievento

- Objetivo: impedir validaciones sobre eventos no asignados.
- Aceptación: el evento se resuelve antes de decidir y se exige permiso `scan_qr` sobre ese evento.
- Pruebas: matriz usuario/evento/token positiva y negativa.
- Resultado: cerrado en código y prueba directa.

### P0-03 — Contratos enterprise

- Objetivo: exponer APIs autenticadas para Edge, vouchers, leads y vehículos, o declarar esos módulos no operativos.
- Complejidad: alta. Dependencias: RBAC, idempotencia y UI/cliente.
- Aceptación: contratos documentados, scoping org/event, auditoría y E2E.
- Resultado: contratos y rutas cerrados; E2E HTTP queda condicionado por el host.

### P0-04 — Certificación PostgreSQL

- Objetivo: validar instalación limpia, upgrade y drift.
- Aceptación: todas las migraciones esperadas aplicadas exactamente una vez y schema diff aprobado.
- Resultado: automatización cerrada; ejecución PostgreSQL real pendiente y no sustituida por SQLite.

### P0-05 — Runtime y suite reproducible

- Objetivo: ejecutar tests del HEAD en CI.
- Aceptación: entorno Python 3.12 bloqueado por lockfile, resultados persistidos y cero gates omitidos críticos.
- Resultado: cerrado en configuración; requiere una ejecución CI para generar evidencia externa.

## P1 — Prioridad alta

- CSRF, cookies seguras, rate limiting y Argon2id/salt individual.
- Autenticación operativa exclusiva para dispositivos `ACTIVE`.
- Secretos obligatorios y rotables sin fallbacks online.
- Cliente Edge real con cola durable.
- Command Center con refresh, freshness y health real.
- Pruebas E2E de flujos A–G.
- Concurrencia PostgreSQL multiinstancia.
- Nuevo endurance 24 h sobre el commit congelado.

Implementados: controles web, autenticación de dispositivos, secretos online,
refresh/freshness del Command Center, bloqueo distribuido de accesos y harness de
endurance. Pendientes de evidencia o producto adicional: cliente Edge dedicado,
E2E HTTP A–G, PostgreSQL multiinstancia real y corrida formal de 24 horas.

## P2 — Mejoras necesarias

- Unificar evolución de esquema SQLite/PostgreSQL.
- Separar HTTP, dominios, DDL, jobs y simulador.
- Sustituir el lock global por transacciones/constraints distribuidos.
- Fijar dependencias y generar SBOM.
- Eliminar duplicación `frontend/static`.
- Completar accesibilidad y estados PRE/LIVE/POST.
- Establecer fuente única de versión y release manifest.

## P3 — Evolución futura

- Cliente Android, si continúa como requisito.
- Integración real de cámaras.
- Herramientas dedicadas para expositores, vouchers y logística.
- Pulido de mapas, controles y analítica avanzada.

## Secuencia y paralelización

Secuencia obligatoria: P0-01/P0-02 → P0-04 → P0-03 → cliente Edge → E2E/concurrencia → endurance → release.

En paralelo pueden avanzar endurecimiento web, versionado, lockfile/SBOM, documentación contractual, accesibilidad y diseño de interfaces, siempre sin fijar contratos antes de cerrar la autoridad de dominio.
