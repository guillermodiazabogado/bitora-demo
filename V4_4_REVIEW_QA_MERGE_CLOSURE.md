# BITORA V4.4 - Review, QA y Merge Closure

## Estado general

PASSED

## Decision

GO MERGED

## Identidad Git

- Fecha de review: 2026-07-28T20:50:04-03:00
- Rama feature: `feature/v4.4-surveys-foundation`
- SHA inicial de feature revisado: `a08e61d98c40d6b6de5f6bbe58820866d5771c3f`
- Rama base: `develop/v4`
- SHA base inicial: `6844156645aac01cefb26a8f526da5f915cb8403`
- SHA final de feature revisado: `296c8c8a2a487615aa508c25e3f37c25bb62265a`
- SHA final de `develop/v4` post-merge: `7ae787a880b32499033d809de96e62764a708bfb`
- PR: `#4 BITORA V4.4 surveys foundation`
- Estado PR pre-review: `OPEN / CLEAN`
- Estado PR final: `MERGED`
- Checks remotos configurados: ninguno reportado por GitHub
- Working tree pre-review: limpio
- Working tree post-merge: limpio

## Inventario funcional

| Capacidad | Implementacion | Pruebas | Riesgo |
| --- | --- | --- | --- |
| Tipos de encuesta | `backend/services/surveys.py`, migracion `019` | `verificar_v4_4_surveys_foundation.py` | Bajo |
| Encuestas por evento | `surveys`, `survey_assignments`, endpoints `server.py` | creacion, asignacion, cierre, archivo | Bajo |
| Versionado | `survey_versions`, `survey_questions`, `survey_question_options` | publicacion e inmutabilidad | Bajo |
| Respuestas identificadas | `survey_response_sessions`, `survey_answers` | participante valido y duplicado rechazado | Bajo |
| Respuestas anonimas | token hasheado y `anonymous_subject_hash` | no exposicion de `participant_id` | Medio controlado |
| Tokens publicos | `survey_access_tokens` | uso unico, hash, restore inactivo | Bajo |
| Resultados | `SurveyService.results` | agregados por version | Bajo |
| Exportacion CSV | `SurveyService.export_csv` | neutralizacion CSV injection y columnas por version | Bajo |
| Backup/restore | `backend/services/backup.py` | remapeo, anonimato y tokens inactivos | Bajo |
| UI minima | `surveys-v4.html` | flujo administrativo basico | Bajo |

## Review tecnico

- Arquitectura: la logica de negocio queda concentrada en `SurveyService`; las rutas HTTP delegan operaciones al servicio.
- Privacidad: el modo anonimo no devuelve ni persiste `participant_id` en sesiones de respuesta anonima.
- Tokens: los tokens completos no se almacenan; solo se conserva hash SHA-256 y `token_hint`.
- Inmutabilidad: las respuestas se vinculan a `version_id`; publicar una version nueva no reescribe respuestas previas.
- Resultados: los agregados se separan por version para evitar mezclar formularios historicos con la version vigente.
- CSV: las exportaciones neutralizan formulas y separan columnas por version cuando hay mas de una version publicada.
- Permisos: las rutas administrativas exigen permisos backend especificos de encuestas.
- Aislamiento: las operaciones validan `organization_id`, `event_id`, asignacion, encuesta, version, participante o token.
- Backup/restore: el restore como evento nuevo remapea entidades y deja tokens restaurados inactivos.

## Hallazgos

| Hallazgo | Criticidad | Estado | Evidencia |
| --- | --- | --- | --- |
| Resultados y CSV podian contar respuestas de versiones anteriores dentro de la version vigente. | Media | Cerrado | `backend/services/surveys.py` separa agregados por version y `verificar_v4_4_surveys_foundation.py` cubre dos versiones con respuestas independientes. |

No quedaron hallazgos criticos, altos ni medios abiertos.

## Validaciones pre-merge

| Validacion | Resultado |
| --- | --- |
| Sintaxis Python | PASSED |
| V4.4 Surveys Foundation | PASSED |
| V4.3 certificados | PASSED |
| V4.2 cierre/elegibilidad | PASSED |
| V4.1 asistencia | PASSED |
| Seguridad basica | PASSED |
| Aislamiento 20 eventos / 1000 participantes | PASSED |
| Restore de evento | PASSED |
| Integridad BITORA | PASSED |
| Convivencia de modulos | PASSED |
| BDF migrate | PASSED |
| BDF health | PASSED |
| BDF smoke-test | PASSED |
| Secret scan | PASSED, 0 secretos detectados |

## Validaciones post-merge sobre develop/v4

| Validacion | Resultado |
| --- | --- |
| Sintaxis Python | PASSED |
| V4.4 Surveys Foundation | PASSED |
| V4.3 certificados | PASSED |
| V4.2 cierre/elegibilidad | PASSED |
| V4.1 asistencia | PASSED |
| Seguridad basica | PASSED |
| Aislamiento 20 eventos / 1000 participantes | PASSED |
| Restore de evento | PASSED |
| Integridad BITORA | PASSED |
| Convivencia de modulos | PASSED |
| BDF migrate | PASSED |
| BDF health | PASSED |
| BDF smoke-test | PASSED |
| Secret scan | PASSED, 0 secretos detectados |

## Alcance confirmado

V4.4 incluye foundation de encuestas: tipos, encuestas, versionado, publicacion, asignacion, respuestas identificadas, respuestas anonimas, tokens publicos hasheados, resultados, CSV seguro, auditoria, RBAC, feature flag y compatibilidad con backup/restore de evento.

## Fuera de alcance confirmado

No se implemento ni modifico: V4.5, release candidate, release estable, Endurance 24h, email, WhatsApp, notificaciones, IA, analisis de sentimiento, logica condicional avanzada, carga de archivos, firma remota ni blockchain.

## Estado recomendado

BITORA V4.4 MERGED TO develop/v4 - READY FOR NEXT VERSION PLANNING
