# V4.1 Architecture Alignment

## Fuentes Leidas

- `BITORA_V4_ATTENDANCE_ARCHITECTURE.md`
- `BITORA_V4_CONCEPTUAL_DATA_MODEL.md`
- `BITORA_V4_API_CONTRACTS_DRAFT.md`
- `BITORA_V4_DOMAIN_EVENTS_CATALOG.md`
- `BITORA_V4_USER_ROLE_MATRIX.md`
- `BITORA_V4_COMPATIBILITY_STRATEGY.md`
- `BITORA_V4_FEATURE_FLAG_POLICY.md`
- `BITORA_V4_TEST_STRATEGY.md`
- `BITORA_V4_IMPLEMENTATION_ROADMAP.md`
- `BITORA_V4_DEPENDENCY_GRAPH.md`
- `RECERTIFICATION_IMPACT_MATRIX.md`
- `BITORA_V4_ARCHITECTURE_DECISION_LOG.md`

## Decision Conservadora

BITORA ya tenia `activity_attendance` y `certificate_eligibility` para asistencia historica ligada a actividades y certificados. V4.1 no reemplaza esas tablas. Agrega `attendance_records`, `attendance_events` y `attendance_corrections` como dominio nuevo, feature-flagged, con ownership explicito.

## Consistencia

El diseno mantiene estado consolidado en `attendance_records` y eventos temporales en `attendance_events`. No implementa cierre, elegibilidad final ni certificados.

## Inconsistencias Resueltas

La arquitectura pedia evaluar si ingreso/egreso eran estados o eventos. Se eligio `attendance_type`/evento de dominio y estado consolidado separado.
