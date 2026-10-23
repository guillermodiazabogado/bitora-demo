# V4.2 Evaluation Algorithm

Version: `attendance_evaluation_algorithm_v1`

Formula:

`attendance_percentage = attended_count / required_count * 100`

El resultado usa `Decimal` y redondeo `ROUND_HALF_UP` a dos decimales.

## Reglas de Calculo

- Solo se consideran registros V4.1 del mismo tenant/evento/scope.
- Se excluyen registros `INVALIDATED`.
- Solo se consideran registros con `occurred_at <= cutoff_at`.
- `PRESENT` cuenta como unidad asistida.
- `PARTIAL` solo cuenta si `allow_partial_attendance = true`.
- Si no hay unidades requeridas, el resultado es `INSUFFICIENT_DATA`.
