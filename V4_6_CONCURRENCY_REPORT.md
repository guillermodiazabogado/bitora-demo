# BITORA V4.6 - Concurrency Report

La validacion usa `idempotency_key` con restriccion unica por organizacion. Reintentos devuelven la decision previa sin duplicar efectos.
