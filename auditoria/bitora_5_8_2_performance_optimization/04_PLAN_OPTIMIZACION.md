# Plan de optimización medible

| Problema | Evidencia | Cambio | Riesgo | Estado |
|---|---|---|---|---|
| Barrido O(N) al confirmar inscripción | consulta de toda la audiencia dentro de la transacción | filtro SQL por `accreditation_id` | bajo | aceptado |
| Dos round-trips por checkout PG | `SELECT 1` + `set_config` en cada conexión prestada | timeout al crear conexión y check nativo del pool | bajo/medio | aceptado |
| Lookup normalizado sin índice | predicados no equivalentes al índice simple | migración 050 | bajo; bloqueo de upgrade en base grande | aceptado técnicamente |
| Lock global QR | cola por proceso | lock granular PostgreSQL | alto | probado y rechazado |
| Benchmark QR mezclado | proporción ALLOW/DENY dependiente del throughput | perfiles válidos y anti-passback separados | bajo | implementado |

Los próximos gates son tres repeticiones sostenidas de diez minutos, saturación controlada y regresiones integrales.
