# BITORA RC1 - Informe de estabilidad

## Resultado

**APTO PARA PILOTO CON OBSERVACIÓN DE INFRAESTRUCTURA**

BITORA queda congelado funcionalmente como RC1. La operación crítica, los paneles, las colas y los backups superaron las pruebas locales. Para un evento real online debe usarse PostgreSQL y almacenamiento persistente; la validación contra una instancia PostgreSQL real requiere configurar `QR_POSTGRES_DSN`.

## Correcciones RC1

- Caché TTL acotada y medible.
- Invalidación de datos después de escrituras.
- QR, acceso, inscripción y cupos excluidos de caché.
- Menos auditorías repetitivas generadas por refrescos.
- NOC y Sala de Control dejan de consultar cuando están ocultos.
- Eliminado el refresco duplicado durante rotación.
- Resúmenes, comunicaciones y diagnóstico reutilizan lecturas recientes.
- Métricas de rutas frecuentes y lentas incorporadas al diagnóstico.
- Índices adicionales para consultas agregadas.
- Scripts de operación continua, carga realista y soak test creados.

## Operación acelerada equivalente a 8 horas

- Participantes: 1.000.
- Terminales: 30.
- Accesos acumulados: 967 concedidos y 20 rechazos controlados.
- Validaciones nuevas medidas: 317.
- QR promedio: 12,4 ms.
- QR p95: 27,2 ms.
- Dashboard promedio: 14,8 ms.
- Dashboard p95: 34,2 ms.
- Data Visualization promedio: 24,1 ms.
- Data Visualization p95: 52,8 ms.
- NOC promedio: 15 ms.
- NOC p95: 25,8 ms.
- Errores técnicos: 0.
- Tokens duplicados: 0.
- Jobs pendientes/fallidos al cierre: 0/0.
- Crecimiento de memoria trazada: 16,7 MB.
- Caché: 49,3% de aciertos bajo invalidación operativa intensa.

## Carga realista

- 276 validaciones distribuidas en ocho franjas.
- QR promedio: 14,1 ms.
- QR p95: 27,6 ms.
- Lecturas agregadas p95: 53,4 ms.
- Jobs completados: 2.
- Jobs pendientes/fallidos: 0/0.
- Crecimiento de memoria: 5,5 MB.

## Soak test

Se ejecutó una corrida continua corta de control:

- 125 ciclos.
- 625 solicitudes.
- Errores: 0.
- Respuesta media: 8,1 ms.
- Crecimiento de memoria: 0,39 MB.
- Crecimiento de logs técnicos: 0.
- Caché: 97,6% de aciertos.

El script queda preparado para una corrida real de 8 horas:

`python soak_test_8h.py --minutes 480 --interval 5`

La corrida real completa no se ejecutó dentro de esta sesión por su duración cronológica.

## Robustez y concurrencia

- 30 estaciones x 3.000 lecturas: 3.000 correctas, 0 errores.
- Rendimiento: 125,4 QR/s.
- p95: 302 ms.
- Máximo: 413 ms.
- Punto de quiebre: no alcanzado hasta el máximo probado.
- Doble lectura del mismo QR: una concesión y 999 rechazos correctos.
- Suite mixta y recuperación: OK.

## Regresión

Pasaron:

- V8 Multi Vertical.
- V7 WhatsApp Meta.
- Asistente WhatsApp existente (`verificar_v5_whatsapp_assistant.py`).
- V6.8 Data Visualization.
- V6.7 Simulador Vivo.
- V6.6 NOC.
- V6 Diagnóstico.
- V6.4 Jobs.
- Integridad punta a punta.
- Convivencia de módulos.
- Robustez.
- Station stress.
- Backup y restauración.
- Readiness productiva.

El archivo solicitado como `verificar_v7_5_whatsapp_assistant.py` no existe en el repositorio; se ejecutó su equivalente actual.

## Riesgos pendientes

- Validar la suite contra una instancia PostgreSQL real antes del primer evento productivo.
- Ejecutar soak test real de 8 horas en la infraestructura definitiva.
- Render gratuito puede dormir, reiniciar o perder almacenamiento efímero; no es apto para operación crítica.
- La caché es local por proceso. Con múltiples instancias deberá migrarse a Redis u otro caché compartido.
- El punto de quiebre superior a 30 estaciones no fue buscado en RC1.

## Conclusión

La aplicación es rápida y predecible bajo la carga probada. La recomendación es avanzar a piloto controlado sobre PostgreSQL, instancia sin suspensión y almacenamiento persistente, manteniendo monitoreo y backup previo al evento.
