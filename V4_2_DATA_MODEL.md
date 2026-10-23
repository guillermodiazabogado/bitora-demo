# V4.2 Data Model

Tablas:

- `attendance_rule_sets`
- `attendance_rule_set_versions`
- `attendance_closures`
- `attendance_evaluations`
- `attendance_evaluation_items`
- `attendance_eligibility_decisions`
- `attendance_overrides`
- `attendance_reopenings`

Todas las entidades principales incluyen `organization_id` y `event_id`.

Relaciones criticas:

- closure -> published rule version;
- evaluation -> closure + participant;
- decision -> evaluation;
- override -> evaluation + decision efectiva;
- reopening -> closure.
