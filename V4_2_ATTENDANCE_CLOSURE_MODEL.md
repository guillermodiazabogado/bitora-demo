# V4.2 Attendance Closure Model

Estados implementados:

- `CLOSING`
- `CLOSED`
- `REOPENED`
- `SUPERSEDED`
- `FAILED`

Transiciones principales:

- crear cierre: `CLOSING` -> `CLOSED`
- error de cierre: `CLOSING` -> `FAILED`
- reapertura: `CLOSED` -> `REOPENED`
- recierre: nuevo `CLOSED` y cierre anterior `SUPERSEDED`

El cierre conserva `cutoff_at`, version de reglas, algoritmo y snapshot hash.
