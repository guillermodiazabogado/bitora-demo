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
| V4-ADR-010 | 2026-07-28 | V4.2 separa hechos, reglas, cierres, evaluaciones y elegibilidad | Certificados futuros requieren evidencia reproducible | Porcentaje mutable en una tabla | Evita recalcular silenciosamente el pasado | Mas tablas e indices aditivos | Aceptada |
| V4-ADR-011 | 2026-07-28 | Motor de reglas limitado y sin codigo dinamico | Reglas de asistencia deben ser explicables | Motor generico con expresiones | Reduce riesgo de seguridad y auditoria | Menor flexibilidad inicial | Aceptada |
| V4-ADR-012 | 2026-07-28 | V4.3 consume elegibilidad efectiva V4.2 | Certificados deben depender de cierres reproducibles | Recalcular asistencia al emitir | Preserva snapshots y trazabilidad | Emision exige decision valida | Aceptada |
| V4-ADR-013 | 2026-07-28 | Documentos emitidos son historicos | Revocacion y reemision no deben sobrescribir evidencia | Reemplazar PDF anterior | Mantiene auditoria y verificacion | Storage y backup preservan versiones | Aceptada |
| V4-ADR-014 | 2026-07-28 | V4.4 separa respuestas anonimas de tokens de acceso | Encuestas anonimas necesitan controlar duplicados sin guardar identidad directa en respuestas | Guardar participante en la respuesta anonima | Reduce exposicion de identidad y mantiene integridad operativa | Tokens separados, hash anonimo y limitaciones documentadas | Aceptada |
| V4-ADR-015 | 2026-07-28 | Las encuestas publicadas responden contra version exacta | Resultados historicos deben ser reproducibles | Responder contra encuesta mutable | Evita cambios retroactivos | Nuevas modificaciones crean nueva version | Aceptada |
