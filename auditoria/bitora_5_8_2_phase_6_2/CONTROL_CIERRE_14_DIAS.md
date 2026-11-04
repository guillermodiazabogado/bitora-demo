# BITORA 5.8.2 — Control de cierre de 14 días

- Inicio: 2026-11-04 16:48 ART
- Día de ejecución: 1/14
- Etapa actual: corrección del gate de lifecycle después de QR R1 incompleto
- Rama: `optimization/5.8.2-qr-latency-phase-6-2`
- Último SHA: `037cf900946cda4a2755cd72ae6e4da8f384cc27`
- Working tree inicial: limpio
- Campaña histórica: `FAIL` terminal, preservada y no reanudable automáticamente
- Procesos/campañas activos al inicio: ninguno
- Evidencia QR histórica SHA-256: `972788ae03447b9db629d9dd47650359f93e4788c888c65b82fe8d5478eac893`
- Última prueba: exploratoria QR válido, 24 lectores, 180,291 s, 21.532/21.532, p95 377,086 ms, p99 406,212 ms, 119,429/s
- Resultado: `PASS` exploratorio; cero errores, timeouts, deadlocks, reinicios u OOM; integridad y reconciliación PASS
- Agentes: backend QR; PostgreSQL/concurrencia; QA/seguridad; coordinador DevOps/certificación
- Próximo paso: validar el lifecycle corregido y lanzar una campaña nueva; el intento incompleto no se reutiliza
- Bloqueos: ninguno
- Tiempo consumido: día 1; diagnóstico, ciclo 1, regresiones y exploratoria de 180 s completados
- Estado global: `EN_EJECUCION`

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
| QR válido 3×600 s | NOT_RUN | Campaña `...037cf90...` terminó FAIL por falso positivo del supervisor durante el reinicio controlado posterior a la carga; sin reporte final, no certificable |
| Anti-passback 16 lectores 3×600 s | NOT_RUN | Gate QR previo |
| Anti-passback 24 lectores 3×600 s | NOT_RUN | Gate APB-16 previo |
| GO-LAB | NOT_RUN | Requiere todos los gates críticos |
