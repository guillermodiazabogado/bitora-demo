# V4.2 RBAC

Permisos nuevos:

- `attendance.rules.read`
- `attendance.rules.manage`
- `attendance.rules.publish`
- `attendance.closure.read`
- `attendance.closure.execute`
- `attendance.closure.reopen`
- `attendance.evaluation.read`
- `attendance.eligibility.read`
- `attendance.eligibility.override`
- `attendance.snapshot.read`

## Mapeo Inicial

- Super Admin: todos.
- Productor: todos.
- Coordinador: lectura de reglas/cierres/evaluaciones/elegibilidad.
- Operadores: sin permisos de cierre ni override por defecto.
- Visualizador: no recibe permisos V4.2 nuevos.
