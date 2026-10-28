# Arquitectura del runner persistente

Se preparó `scripts/persistent_endurance_runner.ps1` con acciones `Start`, `Status` y `Stop`.

El monitor se desacopla mediante `Start-Process` oculto y conserva metadata atómica, PID de monitor y trabajo, heartbeat, checkpoints JSONL, stdout/stderr, SHA esperado, hash de argumentos, reloj monotónico, timeout y archivo de parada. No registra argumentos sensibles en claro.

La ejecución operativa propuesta usa una tarea específica del Programador de tareas de Windows, con usuario actual, `MultipleInstances=IgnoreNew`, máximo de ocho horas y sin reinicio automático de una endurance interrumpida. No se reutilizarán tareas históricas ni checkouts ajenos.

Registrar la tarea es un cambio persistente del equipo y requiere autorización expresa. No se instaló ningún servicio ni runner GitHub.
