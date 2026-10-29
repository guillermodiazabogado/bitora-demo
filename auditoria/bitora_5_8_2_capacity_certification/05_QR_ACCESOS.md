# QR y accesos

Se ejecutó `/api/validate` con sesión, credenciales distintas, contención, ENTRY, anti-passback e idempotencia.

| Configuración | Lectores virtuales | Repeticiones | Respuestas HTTP/s mínimo / promedio | p95 máximo | Errores | Resultado |
|---|---:|---:|---:|---:|---:|---|
| 1 instancia | 24 | 3 | 49,972 / 58,784 | 538,503 ms | 0 | SLO variable |
| 2 instancias | 24 | 3 | 87,558 / 101,709 | 396,841 ms | 0 | PASS |
| 4 instancias | 24 | 3 | 118,544 / 141,933 | 393,106 ms | 0 | PASS |

Anti-passback e idempotencia se preservaron. La carga sostenida reutiliza credenciales: la mayoría de respuestas son rechazos legítimos `ANTI_PASSBACK`, por lo que estas cifras certifican capacidad de responder decisiones, no ingresos autorizados/s. Un control separado de 30 ENTRY simultáneos produjo 1 autorización y 29 rechazos legítimos. Son lectores virtuales HTTP sobre loopback, no hardware ni red de predio.

## Carga sostenida 120 segundos

| Instancias | Lectores | Respuestas | Respuestas/s | p95 | Resultado |
|---:|---:|---:|---:|---:|---|
| 4 | 24 | 11.232 | 93,401 | 622,904 ms | FAIL SLO |
| 2 | 24 | 9.183 | 76,356 | 565,292 ms | FAIL SLO |
| 2 | 12 | 6.755 | 56,206 | 554,029 ms | FAIL SLO |
| 2 | 8 | 9.247 | 76,983 | 162,662 ms | PASS observado una vez |

El punto QR8 no se repitió tres veces; es capacidad observada, no certificación estadística repetida.
