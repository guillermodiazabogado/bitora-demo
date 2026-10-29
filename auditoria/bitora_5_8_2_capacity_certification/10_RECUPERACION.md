# Recuperación

Cada ejecución fresca reinició una instancia después de retirar la carga, esperó `/ready` y completó una inscripción. Resultado: PASS, aproximadamente 3 segundos hasta disponibilidad funcional posterior al reinicio.

No prueba failover con operaciones en vuelo ni RTO integral. No hubo operaciones aceptadas perdidas, reinicios inesperados, OOM, deadlocks ni duplicados. La matriz acumulativa no recuperó su última inscripción por presión de conexiones entre celdas; se conserva como saturación del laboratorio, no como fallo de integridad de los puntos frescos.
