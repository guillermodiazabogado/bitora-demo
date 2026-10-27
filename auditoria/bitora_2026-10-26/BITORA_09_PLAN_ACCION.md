# BITORA — Plan de acción priorizado y estado de ejecución

Fecha de cierre: 2026-10-27. Los resultados corresponden al baseline
`116a612f7f14ae543b2bff112b503fa15b61665d`. No implican despliegue productivo.

| Ítem | Estado actual | Evidencia reproducible | Pendiente externo |
|---|---|---|---|
| P0-01 Autoridad de accesos | Cerrado y verificado | verificadores de autoridad/activación, concurrencia y CI verde | Monitoreo productivo continuo |
| P0-02 Aislamiento multievento | Implementado y validado | `verificar_p0_access_event_scope.py`, matriz 20 eventos/1000 participantes | Ninguno para alcance local |
| P0-03 Contratos enterprise | Implementados y verificados | V5.4/V5.5/V5.6, Edge y E2E HTTP CI | Clientes operativos dedicados |
| P0-04 Certificación PostgreSQL | Cerrado | CI `40387964080`, 50 migraciones, clean/upgrade equivalentes | Repetir por release |
| P0-05 Runtime reproducible | Cerrado | Python 3.12, lockfile, CI, SBOM y Docker build | Renovación periódica de dependencias |
| P1 Seguridad web/dispositivos | Cerrado para el alcance evaluado | Argon2id, CSRF, cookie segura, rate limit, dispositivos `ACTIVE`, E2E CI | Pruebas periódicas y rotación operativa |
| P1 Concurrencia | Cerrado para el alcance evaluado | 30 ENTRY: 1 ALLOW/29 anti-passback; advisory lock; CI PostgreSQL | Ensayo multiinstancia de infraestructura antes de gran escala |
| P1 Endurance | Cerrado | 24 h, 159.226 operaciones, integridad `ok`, cero fallos | Repetir sobre cada release candidate |
| P2 Versionado/SBOM | Cerrado | `VERSION`, manifest, SBOM CycloneDX y artefactos CI | Publicación por release |

Los tres gates externos definidos por la auditoría —PostgreSQL real, E2E HTTP y
endurance 24 h— terminaron satisfactoriamente. La autorización de despliegue sigue
requiriendo revisión de configuración, secretos, capacidad e infraestructura del
entorno productivo concreto.

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
- Resultado: contratos, rutas y E2E HTTP cerrados en CI.

### P0-04 — Certificación PostgreSQL

- Objetivo: validar instalación limpia, upgrade y drift.
- Aceptación: todas las migraciones esperadas aplicadas exactamente una vez y schema diff aprobado.
- Resultado: cerrado en PostgreSQL 16 CI; clean/upgrade equivalentes y ledger exacto.

### P0-05 — Runtime y suite reproducible

- Objetivo: ejecutar tests del HEAD en CI.
- Aceptación: entorno Python 3.12 bloqueado por lockfile, resultados persistidos y cero gates omitidos críticos.
- Resultado: cerrado; ejecución CI `40387964080` exitosa y artefactos conservados.

## P1 — Prioridad alta

- CSRF, cookies seguras, rate limiting y Argon2id/salt individual.
- Autenticación operativa exclusiva para dispositivos `ACTIVE`.
- Secretos obligatorios y rotables sin fallbacks online.
- Cliente Edge real con cola durable.
- Command Center con refresh, freshness y health real.
- Pruebas E2E de flujos A–G.
- Concurrencia PostgreSQL multiinstancia.
- Nuevo endurance 24 h sobre el commit congelado.

Implementados y verificados: controles web, autenticación de dispositivos, secretos
online, refresh/freshness del Command Center, bloqueo distribuido, E2E HTTP,
PostgreSQL y endurance formal de 24 horas. Permanecen como evolución de producto
el cliente Edge dedicado y ensayos de infraestructura multiinstancia a escala.

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
