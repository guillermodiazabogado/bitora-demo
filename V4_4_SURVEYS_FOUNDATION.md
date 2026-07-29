# BITORA V4.4 - Surveys Foundation

## Dominio

El modulo introduce:

- `survey_types`
- `surveys`
- `survey_versions`
- `survey_questions`
- `survey_question_options`
- `survey_assignments`
- `survey_access_tokens`
- `survey_response_sessions`
- `survey_answers`
- `survey_answer_options`

La logica de negocio vive en `backend/services/surveys.py`. Los endpoints HTTP delegan en `SurveyService`.

## Estados

- Encuesta: `DRAFT`, `PUBLISHED`, `OPEN`, `CLOSED`, `ARCHIVED`.
- Version: `DRAFT`, `PUBLISHED`, `RETIRED`.
- Asignacion: `DRAFT`, `OPEN`, `CLOSED`, `DISABLED`, `ARCHIVED`.
- Sesion: `IN_PROGRESS`, `SUBMITTED`, `EXPIRED`, `CANCELLED`.

Una version publicada es inmutable. Cualquier cambio posterior debe crear una nueva version.

## Preguntas Permitidas

- `SHORT_TEXT`
- `LONG_TEXT`
- `SINGLE_CHOICE`
- `MULTIPLE_CHOICE`
- `SCALE`
- `YES_NO`

No se implementan matrices, archivos, multimedia, geolocalizacion ni logica condicional compleja.

## Respuestas

Las respuestas identificadas pueden guardar `participant_id`.

Las respuestas anonimas no guardan `participant_id` en `survey_response_sessions`; usan `anonymous_subject_hash` no reversible y tokens separados en `survey_access_tokens` para controlar acceso y duplicados.

## Resultados y Exportacion

Los resultados administrativos incluyen conteos, distribucion por opcion, promedio/min/max de escala y textos libres paginados de forma simple.

La exportacion CSV neutraliza celdas que empiezan con `=`, `+`, `-` o `@` para reducir riesgo de CSV injection.

## Feature Flag

El modulo se controla con:

- `BITORA_SURVEYS_V4_ENABLED=true`
- feature flag `surveys_v4_enabled` por plataforma, organizacion o evento.

Cuando el flag esta apagado, los endpoints administrativos y el acceso publico controlado quedan bloqueados.
