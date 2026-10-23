# V4.2 Snapshot Specification

Snapshot schema:

`attendance_closure_snapshot_v1`

Incluye:

- organization_id;
- event_id;
- activity_id opcional;
- scope_type;
- rule_set_version_id;
- rule_configuration_hash;
- cutoff_at;
- algorithm_version;
- actor;
- evaluaciones;
- registros considerados por evaluacion.

El hash se calcula sobre JSON normalizado con claves ordenadas.
