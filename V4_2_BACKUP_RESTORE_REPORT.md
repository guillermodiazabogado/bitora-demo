# V4.2 Backup Restore Report

Tablas V4.2 incluidas en backup de evento:

- `attendance_rule_sets`
- `attendance_rule_set_versions`
- `attendance_closures`
- `attendance_evaluations`
- `attendance_evaluation_items`
- `attendance_eligibility_decisions`
- `attendance_overrides`
- `attendance_reopenings`

Remapeos preparados:

- rule_set_id;
- current_version_id;
- rule_set_version_id;
- closure_id;
- supersedes_closure_id;
- evaluation_id;
- override_id;
- attendance_record_id;
- participant_id;
- accreditation_id;
- activity_id.

Validacion:

- `verificar_v4_2_attendance_closure_eligibility.py`: PASSED.
- `verificar_event_restore.py`: PASSED.
