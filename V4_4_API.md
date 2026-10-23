# BITORA V4.4 - API

## Administracion

- `GET /api/survey-types?event_id={id}`
- `POST /api/survey-types`
- `GET /api/surveys?event_id={id}`
- `POST /api/surveys`
- `GET /api/events/{event_id}/surveys/{survey_id}`
- `POST /api/surveys/{survey_id}/versions`
- `POST /api/surveys/{survey_id}/versions/{version_id}/publish`
- `POST /api/events/{event_id}/surveys/{survey_id}/assign`
- `POST /api/events/{event_id}/surveys/{survey_id}/assignments/{assignment_id}/close`
- `POST /api/events/{event_id}/surveys/{survey_id}/archive`
- `GET /api/events/{event_id}/surveys/{survey_id}/results`
- `GET /api/events/{event_id}/surveys/{survey_id}/export.csv`

## Publico Controlado

- `GET /api/public/surveys/access/{token}`
- `POST /api/public/surveys/access/{token}/start`
- `POST /api/public/surveys/sessions/{session_id}/submit`

Los endpoints publicos no exponen IDs internos innecesarios, auditorias, resultados, permisos, hashes ni identidad de otros participantes.

## Permisos

- `surveys.types.read`
- `surveys.types.manage`
- `surveys.read`
- `surveys.create`
- `surveys.edit`
- `surveys.publish`
- `surveys.assign`
- `surveys.open`
- `surveys.close`
- `surveys.results.view`
- `surveys.export`
- `surveys.archive`
- `surveys.audit.view`
