# BITORA 5.8.2 — Control de cierre de 14 días

- Inicio: 2026-11-04 16:48 ART
- Día de ejecución: 1/14
- Etapa actual: cierre técnico por FAIL sostenido de QR válido R2
- Rama: `optimization/5.8.2-qr-latency-phase-6-2`
- Último SHA: `845a0a8dfbc0b5e74e1a3abb6c04b6f0ad508c26`
- Working tree inicial: limpio
- Campaña histórica: `FAIL` terminal, preservada y no reanudable automáticamente
- Procesos/campañas activos al inicio: ninguno
- Evidencia QR histórica SHA-256: `972788ae03447b9db629d9dd47650359f93e4788c888c65b82fe8d5478eac893`
- Última prueba: exploratoria QR válido, 24 lectores, 180,291 s, 21.532/21.532, p95 377,086 ms, p99 406,212 ms, 119,429/s
- Resultado: `PASS` exploratorio; cero errores, timeouts, deadlocks, reinicios u OOM; integridad y reconciliación PASS
- Agentes: backend QR; PostgreSQL/concurrencia; QA/seguridad; coordinador DevOps/certificación
- Próximo paso: nueva hipótesis de optimización solo con evidencia de profiling; no repetir esta campaña sin cambios
- Bloqueos: QR válido 24 lectores no cumple p95 <=500 ms de forma repetible
- Tiempo consumido: día 1; diagnóstico, optimización, regresiones, runner y dos corridas sostenidas completados
- Estado global: `NO-GO-LAB`

## Gates

| Gate | Estado | Evidencia |
|---|---|---|
| Preflight único | PASS | Rama/SHA limpios; sin runner ni contenedores activos |
| Diagnóstico backend | PASS | Ruta QR reconstruida; no se tocaron locks ni invariantes |
| Diagnóstico PostgreSQL | PASS | Hotspot: introspección de `audit_logs` por cada autorización |
| Suite de regresión mínima | PASS | Docker: autoridad, scope, concurrencia, state engine, zonas, multiinstancia y matriz HTTP |
| Baseline breve comparable | PASS | 24 lectores/60 s: 7.394/7.394; p95 312,014 ms; p99 439,515 ms; 122,733/s |
| Optimización ciclo 1 | KEEP | Sin introspección por auditoría; 180 s: p95 377,086 ms; p99 406,212 ms; 119,429/s |
| Runner autónomo | PASS SMOKE | Lifecycle `STARTING→READY→RUNNING→FINISHED`; SHA limpio; 1.192/1.192; p95 286,388 ms; cero errores |
| QR válido 3×600 s | FAIL | R1 PASS: p95 497,053 ms, 52.573/52.573; R2 FAIL: p95 608,861 ms, 44.802/44.802; R3 NOT_RUN |
| Anti-passback 16 lectores 3×600 s | NOT_RUN | Gate QR previo |
| Anti-passback 24 lectores 3×600 s | NOT_RUN | Gate APB-16 previo |
| GO-LAB | FAIL | SLO QR no repetible; supervisor detuvo correctamente la secuencia |
