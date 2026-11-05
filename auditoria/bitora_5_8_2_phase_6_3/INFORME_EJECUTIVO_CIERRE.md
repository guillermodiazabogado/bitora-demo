# BITORA 5.8.2 — Cierre técnico Fase 6.3

## Decisión

**GO-LAB** para laboratorio. Producción permanece **NO-GO**.

El candidato evaluado es `33c13cf0aaf79baae4e28d2603cb0732a10dbde2`. La campaña terminó en `PASS` con 9 de 9 corridas completas. No se promediaron p95 ni se convirtieron pruebas no ejecutadas en PASS.

## Cambios del candidato

- Eliminación de dos readbacks PostgreSQL no consumidos en la ruta QR.
- Gate PostgreSQL configurable, certificado con el valor conservador de una transacción QR por instancia.
- Advisory lock alineado con `organization/event/entity_id`, con fallback por acreditación, para preservar anti-passback cuando una identidad tiene más de una credencial.
- Telemetría temporal y por contenedor para separar aplicación, PostgreSQL y entorno.

## Resultado terminal

| Prueba | Estado | Duración s | Ops | Autorizadas | Rechazos | Errores | ops/s | p95 ms | p99 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| qr-valid-24-r1 | PASS | 601.598 | 52666 | 52666 | 0 | 0 | 87.544 | 484.772 | 779.586 |
| qr-valid-24-r2 | PASS | 601.613 | 52043 | 52043 | 0 | 0 | 86.506 | 446.075 | 1107.782 |
| qr-valid-24-r3 | PASS | 601.813 | 50326 | 50326 | 0 | 0 | 83.624 | 484.086 | 1496.237 |
| qr-antipassback-16-r1 | PASS | 601.9 | 46721 | 0 | 46721 | 0 | 77.623 | 377.196 | 1300.452 |
| qr-antipassback-16-r2 | PASS | 601.944 | 52446 | 0 | 52446 | 0 | 87.128 | 293.775 | 656.398 |
| qr-antipassback-16-r3 | PASS | 602.047 | 52256 | 0 | 52256 | 0 | 86.797 | 289.149 | 1033.416 |
| qr-antipassback-24-r1 | PASS | 601.852 | 48558 | 0 | 48558 | 0 | 80.681 | 483.272 | 2241.233 |
| qr-antipassback-24-r2 | PASS | 603.89 | 50773 | 0 | 50773 | 0 | 84.077 | 466.738 | 1377.687 |
| qr-antipassback-24-r3 | PASS | 601.909 | 49656 | 0 | 49656 | 0 | 82.498 | 474.333 | 1348.44 |

Motivo de detención: `ninguno`. Las inscripciones históricas R1/R2/R3 permanecen preservadas; producción requiere todavía staging, infraestructura, red, dispositivos físicos y simulacro operativo autorizados.
