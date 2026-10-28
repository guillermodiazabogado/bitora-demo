# Validación del runner

Estado: **PASS local, pendiente de registro operativo**.

El wrapper implementa el ciclo requerido y su verificador cubre finalización normal, consulta, parada controlada y presencia de siete archivos de evidencia. La revisión independiente detectó y corrigió una carrera de estado `starting` y una incompatibilidad entre Windows PowerShell 5.1 y el monitor.

El monitor ahora usa explícitamente PowerShell 7, guarda stdout/stderr propios y conserva evidencia si falla. Validación: cinco ejecuciones consecutivas del agente y una repetición independiente desde `powershell.exe`, todas PASS con estados `complete` y `stopped`, sin argumentos en claro.
