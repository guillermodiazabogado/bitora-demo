# Cambios implementados

## Conservados

- Consulta dirigida para confirmación de inscripción.
- Índices de búsqueda QR normalizada y hash enterprise (`050_access_lookup_indexes.sql`).
- Configuración de `statement_timeout` al crear conexiones; se eliminaron dos round-trips por checkout.
- Perfiles QR sostenidos `valid` y `antipassback` en el harness.
- Regresiones para targeting de confirmación e índices.

## Resultado preliminar

- Inscripción: 54,736/s en `cb0570a`, contra 42,705/s inicial (+28,2 %), p95 833,120 ms, cero fallos.
- QR histórico 12 lectores: 83,329/s, p95 234,152 ms, cero fallos.
- QR válido 24 lectores, 60 s: 82,89 accesos/transiciones autorizadas/s, p95 444,13 ms, PASS preliminar.
- Anti-passback 24 lectores, 60 s: 85,20 decisiones/s, p95 505,03 ms, integridad PASS pero SLO de latencia FAIL.

Estos puntos todavía no sustituyen las tres repeticiones de diez minutos.
