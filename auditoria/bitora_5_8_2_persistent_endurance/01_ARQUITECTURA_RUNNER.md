# Arquitectura del runner persistente

Se preparó `scripts/persistent_endurance_runner.ps1` con acciones `Start`, `Status` y `Stop`.

El monitor se desacopla mediante `Start-Process` oculto y conserva metadata atómica, PID de monitor y trabajo, heartbeat, checkpoints JSONL, stdout/stderr, SHA esperado, hash de argumentos, reloj monotónico, timeout y archivo de parada. No registra argumentos sensibles en claro.

La ejecución operativa utilizó la tarea específica `BITORA-5.8.2-Endurance-6H-f9dc15e` del Programador de tareas de Windows, con usuario actual, `MultipleInstances=IgnoreNew`, máximo de ocho horas y sin reinicio automático de una endurance interrumpida. No se reutilizaron tareas históricas ni checkouts ajenos.

El usuario autorizó el registro y la instalación de Docker Engine en Ubuntu WSL. No se instaló ningún runner GitHub ni se utilizaron recursos productivos.

Tras conservar la evidencia y confirmar el cierre, la tarea programada específica fue retirada para no dejar un lanzador obsoleto activo. Docker Engine permanece disponible como entorno de laboratorio autorizado.
