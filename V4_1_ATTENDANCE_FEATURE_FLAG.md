# V4.1 Attendance Feature Flag

## Flag

`attendance_v4_enabled`

## Scopes

- platform
- organization
- event

## Activacion

Puede activarse por variable `BITORA_ATTENDANCE_V4_ENABLED=true` o por tabla `feature_flags`.

## Flag OFF

Los endpoints V4 responden `ATTENDANCE_FEATURE_DISABLED`; el sistema historico sigue funcionando.

## Flag ON

Solo habilita funcionalidad. No omite RBAC, auditoria ni validaciones tenant.
