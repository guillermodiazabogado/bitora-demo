# Capacidad certificada

Capacidad de ráfaga corta repetible en laboratorio sobre este host y PostgreSQL 16:

| Configuración | Inscripción certificada | Concurrencia de carga | QR certificado | Condición |
|---|---:|---:|---:|---|
| 1 instancia | ≥27,817 completas/s | 25 workers | No a 24 lectores (p95 variable) | sin HA |
| 2 instancias | ≥41,773 completas/s | 50 workers | ≥87,558 decisiones HTTP/s, 24 lectores | PASS corto |
| 4 instancias | ≥52,412 completas/s | 50 workers | ≥118,544 decisiones HTTP/s, 24 lectores | PASS corto |

Se informa el mínimo de tres repeticiones cortas, no el mejor resultado. Las decisiones QR incluyen mayormente rechazos anti-passback y no equivalen a accesos autorizados/s. La cifra 72–79 inscripciones/s de 4×100 es máxima observada y no capacidad certificada.

Capacidad sostenida reproducida durante 120 segundos:

- 2 instancias / 25 workers: **≥38,045 inscripciones completas/s**, tres corridas, p95 ≤1.350,353 ms.
- 2 instancias / 8 lectores virtuales: **76,983 decisiones/s**, p95 162,662 ms, una corrida; observado, pendiente repetición.
- 12 y 24 lectores virtuales: SLO FAIL sostenido para la mezcla ensayada.
