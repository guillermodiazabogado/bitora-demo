# Inscripciones

Flujo medido: `GET evento → POST registro → GET portal → GET QR SVG`. No se usaron inserciones SQL como sustituto.

| Configuración | Workers | Repeticiones | Throughput mínimo / promedio | p95 máximo | p99 máximo | Resultado |
|---|---:|---:|---:|---:|---:|---|
| 1 instancia | 25 | 3 | 27,817 / 28,095 insc/s | 901,430 ms | 1.246,429 ms | PASS |
| 2 instancias | 50 | 3 | 41,773 / 41,832 insc/s | 1.855,103 ms | 2.121,688 ms | PASS |
| 4 instancias | 50 | 3 | 52,412 / 52,553 insc/s | 1.162,873 ms | 1.209,812 ms | PASS |
| 4 instancias | 100 | 3 | 72,019 / 76,663 insc/s | 2.421,011 ms | 2.486,329 ms | NO CERTIFICADO |

Todas las solicitudes válidas de los puntos frescos terminaron sin error técnico ni duplicados. El SLO previo fue éxito ≥99,9 % y p95 ≤2.000 ms. Los workers son operaciones cerradas concurrentes, no usuarios humanos autenticados.

## Carga sostenida 120 segundos

Con 2 instancias y 25 workers se completaron tres ejecuciones: 4.611–4.937 altas por corrida, mínimo 38,045 inscripciones/s, p95 máximo 1.350,353 ms y cero fallos. Este es el nivel sostenido reproducido.

4 instancias y 50 workers completaron 7.058/7.058 altas a 55,983/s, pero p95 fue 2.258,187 ms: integridad PASS, SLO FAIL.
