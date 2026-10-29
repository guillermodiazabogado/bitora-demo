# Línea base reproducida

La línea base fue ejecutada, no extrapolada. El flujo de inscripción incluyó consulta de evento, alta, persistencia, portal y QR. El flujo QR histórico mezcló autorizaciones y rechazos anti-passback, por lo que se conserva como referencia pero no como capacidad de accesos autorizados.

| SHA | Instancias | Workers | Inscripciones/s | p95 inscripción | Lectores | Decisiones QR/s | p95 QR | Integridad |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `f1098e2` | 2 | 25 | 42,705 | 790,696 ms | 12 | 103,588 | 135,589 ms | PASS |

La variación del host observada entre corridas obliga a repetir los puntos candidatos al menos tres veces antes de recertificar capacidad.
