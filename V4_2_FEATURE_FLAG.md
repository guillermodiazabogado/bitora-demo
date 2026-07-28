# V4.2 Feature Flag

Flag:

`attendance_closure_eligibility_v4_enabled`

Variable de entorno:

`BITORA_ATTENDANCE_CLOSURE_ELIGIBILITY_V4_ENABLED=true`

Dependencia:

`attendance_v4_enabled` debe estar activo.

Flag OFF:

- APIs V4.2 responden con `ATTENDANCE_FEATURE_DEPENDENCY_DISABLED`.
- V4.1 sigue operativa.
