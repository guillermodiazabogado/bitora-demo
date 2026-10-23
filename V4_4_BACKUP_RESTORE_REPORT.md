# BITORA V4.4 - Backup and Restore

## Cobertura

El backup de evento incluye:

- tipos de encuesta;
- encuestas;
- versiones;
- preguntas;
- opciones;
- asignaciones;
- tokens de acceso;
- sesiones de respuesta;
- respuestas;
- opciones seleccionadas;
- auditoria relacionada.

## Restore como Nuevo Evento

El restore remapea:

- `survey_type_id`;
- `survey_id`;
- `version_id`;
- `question_id`;
- `option_id`;
- `assignment_id`;
- `session_id`;
- `answer_id`;
- `participant_id`;
- `activity_id`;
- `event_id`.

Los tokens restaurados se regeneran y quedan como `RESTORED_INACTIVE`, evitando reutilizacion automatica y preservando el modo seguro.

## Resultado Validado

`verificar_v4_4_surveys_foundation.py` valida restore como nuevo evento con respuestas identificadas y anonimas, preservacion de relaciones y anonimato.
