# Diagnóstico de concurrencia

## Hallazgos

1. `DB_LOCK` serializa las transacciones de inscripción y QR por proceso.
2. PostgreSQL ya protege una acreditación con `pg_advisory_xact_lock`, pero retirar el lock global aumentó la contención y empeoró el benchmark en este entorno; el cambio fue revertido.
3. La confirmación de una inscripción recorría y ordenaba toda la audiencia del evento para seleccionar una sola acreditación. El costo crecía con el dataset dentro de la transacción.
4. El pool ejecutaba dos round-trips de control por cada checkout.
5. El benchmark QR histórico producía una mezcla dependiente del throughput y no distinguía accesos válidos de anti-passback.

## Experimentos rechazados

- Paralelismo PostgreSQL sin `DB_LOCK`: integridad PASS, pero QR bajó de 103,588 a 81,47 decisiones/s y p95 subió de 135,589 a 280,60 ms. Revertido.
- Eliminación de consultas redundantes del hot path: integridad PASS, pero no superó la variabilidad y empeoró el punto comparable. Revertido.

No se conservaron optimizaciones que solo parecieran correctas por inspección.
