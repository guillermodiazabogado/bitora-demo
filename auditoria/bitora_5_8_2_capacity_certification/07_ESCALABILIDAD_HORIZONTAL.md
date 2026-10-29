# Escalabilidad horizontal

Comparación fresca con 50 workers:

| Instancias | Inscripciones/s | p95 inscripción | QR/s con 24 lectores |
|---:|---:|---:|---:|
| 1 | 28,780 (observado una vez a 50) | 1.967,780 ms | ~65–70 |
| 2 | 41,773–41,878 | ≤1.855,103 ms | 87,558–124,423 |
| 4 | 52,412–52,790 | ≤1.162,873 ms | 118,544–187,773 |

El aumento fue ~45 % de 1 a 2 instancias y ~26 % de 2 a 4: positivo pero no lineal. El pico de 79,076 inscripciones/s con 4×100 no se certifica por variabilidad.
