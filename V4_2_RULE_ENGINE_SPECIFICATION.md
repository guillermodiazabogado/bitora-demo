# V4.2 Rule Engine Specification

El motor es especifico para asistencia y acepta solo claves aprobadas.

## Reglas Soportadas

- `minimum_attendance_percentage`: Decimal entre 0 y 100.
- `minimum_attended_activities`: entero no negativo.
- `mandatory_activity_ids`: lista de IDs de actividades del evento.
- `allow_partial_attendance`: booleano.
- `require_event_presence`: booleano.
- `require_all_mandatory_activities`: booleano.
- `eligibility_mode`: `ALL` o `ANY`.
- `allow_manual_override`: booleano.

Campos desconocidos se rechazan con `ATTENDANCE_RULE_CONFIGURATION_INVALID`.

## Seguridad

No hay ejecucion dinamica. La configuracion se normaliza y se hashea con JSON ordenado.
