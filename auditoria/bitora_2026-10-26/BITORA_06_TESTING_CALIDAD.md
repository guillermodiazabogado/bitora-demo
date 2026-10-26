# BITORA — Testing, calidad y rendimiento

## Inventario

Se identificaron 137 scripts Python asociados a verificación, estrés, endurance o certificación. La mayoría son scripts ejecutables independientes, no una suite estándar pytest/unittest con cobertura consolidada.

## Ejecución de esta auditoría

| Comprobación | Resultado |
|---|---|
| Reconocimiento Git | PASS |
| `git diff --check` | PASS |
| Sintaxis `frontend/app.js` | PASS |
| Sintaxis `frontend/noc.js` | PASS |
| Sintaxis `static/app.js` | PASS |
| `static/noc.js` | NO EXISTE |
| Pruebas Python | BLOQUEADAS: runtime no ejecutable |
| PostgreSQL/R2 | NO EJECUTADAS |
| Stress/endurance | NO EJECUTADAS |
| Restore/migraciones | NO EJECUTADAS |

## Evidencia histórica

- Informes antiguos declaran 30 estaciones y 3.000/3.000 lecturas.
- Informes de estrés declaran 10.000 operaciones.
- Endurance `ENDURANCE-24H-20260810-214813`: FAILED después de 24,13 horas.
- Endurance R2 posterior: PASSED sobre otro SHA y staging externo, con revisión externa pendiente.
- Resultados V5 están bajo `docs/enterprise-evolution/`, carpeta local no versionada.
- Un resultado V5.8 registra una simulación de 100 dispositivos con cero operaciones, que requiere aclaración.

Ninguno de estos antecedentes certifica el HEAD auditado.

## CI

La CI instala dependencias, compila `backend`, `server.py` y `verificar_v4.py`, ejecuta secret scan y construye Docker. No ejecuta la matriz funcional V5 ni pruebas E2E, concurrencia o PostgreSQL.

## Requisitos de recertificación

1. Runtime Python 3.12 reproducible.
2. Suite agrupada por dominio con salidas JUnit/JSON.
3. Cobertura de API, no solo llamadas directas a servicios.
4. PostgreSQL real y migraciones desde cero/upgrade.
5. Concurrencia multiinstancia.
6. Dispositivos/Edge reales.
7. Endurance 24 h sobre el mismo commit candidato.
