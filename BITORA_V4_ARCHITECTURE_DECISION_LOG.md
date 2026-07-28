# BITORA V4 Architecture Decision Log

| ID | Fecha | Decision | Contexto | Alternativas | Motivo | Impacto | Estado |
|---|---|---|---|---|---|---|---|
| V4-ADR-001 | 2026-07-28 | V4 empieza como diseno documental | RC esta certificada y congelada | Implementar directo | Evita romper evidencia | Runtime changes 0 | Aceptada |
| V4-ADR-002 | 2026-07-28 | Asistencia es primer dominio | Certificados y analytics dependen de presencia real | Empezar por comunicaciones o analytics | Reduce dependencia aguas abajo | V4.1 bloqueante | Aceptada |
| V4-ADR-003 | 2026-07-28 | Todo nuevo objeto tiene ownership explicito | Multi-tenant certificado no debe degradarse | Ownership inferido | Evita cruces | Mas validaciones backend | Aceptada |
| V4-ADR-004 | 2026-07-28 | Feature flags por plataforma/org/evento | Rollout progresivo | Activacion global | Reduce riesgo operativo | Requiere auditoria de flags | Aceptada |
| V4-ADR-005 | 2026-07-28 | Automatizaciones solo supervisadas | Riesgo de efectos externos | Automatizacion autonoma | Mantiene explicabilidad | Menos automatismo inicial | Aceptada |
| V4-ADR-006 | 2026-07-28 | Certificados dependen de elegibilidad versionada | Reglas deben ser reproducibles | Calculo dinamico sin version | Auditoria y reemision coherentes | Requiere snapshot de regla | Aceptada |
| V4-ADR-007 | 2026-07-28 | Rutas legacy se conservan | Frontend actual depende de contratos | Reemplazo inmediato | Compatibilidad | APIs nuevas seran incrementales | Aceptada |
| V4-ADR-008 | 2026-07-28 | V4.1 usa tablas nuevas paralelas a `activity_attendance` | La asistencia historica esta ligada a certificados | Reusar tabla historica | Evita romper compatibilidad y separa cierre/elegibilidad futuros | Requiere puente en reportes | Aceptada |
| V4-ADR-009 | 2026-07-28 | Idempotencia scoped por organizacion | Multi-tenant requiere aislamiento de reintentos | Key global | Evita colisiones entre tenants | Unique organization_id + idempotency_key | Aceptada |
