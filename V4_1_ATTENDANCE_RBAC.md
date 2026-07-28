# V4.1 Attendance RBAC

## Permisos

- `attendance.read`
- `attendance.record`
- `attendance.correct`
- `attendance.invalidate`
- `attendance.read_audit`

## Mapeo Inicial

- Super Admin: todos.
- Productor: todos.
- Coordinador: lectura, registro, correccion y auditoria.
- Operador de recepcion: lectura.
- Operador de acceso: registro.
- Visualizador: lectura.

## Backend

Cada endpoint usa `require_event_permission`. La UI no es fuente de autorizacion. El evento determina organizacion y scope.
