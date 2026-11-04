# Runner autónomo — Fase 6.2

Estado: preparado, no lanzado. La configuración conserva marcadores deliberados hasta congelar el SHA y crear un worktree certificado limpio.

## Secuencia cerrada

1. QR válido, 24 lectores: R1/R2/R3.
2. Anti-passback, 16 lectores: R1/R2/R3.
3. Anti-passback, 24 lectores: R1/R2/R3.

Cada corrida dura al menos 600 segundos y debe cumplir p95 <= 500 ms, cero errores técnicos, cero deadlocks, integridad y semántica de perfil. El supervisor detiene la campaña ante el primer FAIL.

## Congelación y lanzamiento

1. Crear un worktree separado, limpio y detached en el SHA candidato.
2. Reemplazar `cert_root` y `expected_sha` en `phase62_campaign_config.json`.
3. Ejecutar `python3 test_phase62_supervisor.py` dentro de WSL.
4. Lanzar `python3 phase62_campaign_supervisor.py` mediante una tarea programada de Windows sin límite de duración.

La evidencia se escribe fuera del worktree candidato, bajo `evidence/<campaign_id>/`. El checkpoint es atómico y el lock rechaza un segundo supervisor. Una campaña terminal no se reinicia automáticamente. Una interrupción no se convierte en PASS: la ausencia de reporte/lifecycle completo produce FAIL y exige una reanudación administrativa nueva, no implementada como inicio automático.

## Límites

- El script no crea ni modifica tareas programadas.
- No se inició ninguna carga.
- La supervivencia al cierre de Codex depende de que el proceso sea lanzado por Task Scheduler.
- Un reinicio del sistema durante carga deja evidencia incompleta y requiere revisión antes de un nuevo intento.
