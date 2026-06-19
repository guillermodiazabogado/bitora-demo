# BITORA RC1 - Rendimiento de base de datos

## Estado

La revisión RC1 confirma que la operación crítica mantiene tiempos bajos y que la mayor carga de lectura proviene de paneles agregados, no de QR ni recepción.

## Endpoints más frecuentes

Medición de operación acelerada equivalente a 8 horas:

| Endpoint | Solicitudes | Tiempo medio observado |
|---|---:|---:|
| `/api/validate` | 329 | 8,77 ms |
| `/api/summary` | 192 | 10,81 ms |
| `/api/reports/visual-summary` | 96 | 23,40 ms |
| `/api/data-visualization` | 96 | 16,29 ms |
| `/api/diagnostics/status` | 32 | 4,55 ms |
| `/api/public-display` | 32 | 20,72 ms |

## Consultas más costosas

1. Resumen visual: agrega acreditaciones, accesos, reservas, asistencia, salas, captación y comunicaciones.
2. Pantalla pública: combina actividades, salas, estados y configuración visible.
3. Data Visualization: genera series, mapas de calor, funnel, rankings y forecast.
4. Resumen operativo: consolida acreditaciones, reservas, accesos y asistencia.

Estas consultas son de lectura y no participan en decisiones críticas. Se protegen con TTL corto y se invalidan ante cambios.

## Optimización aplicada

- Caché en memoria acotada para eventos, configuración, resumen, pantalla pública, comunicaciones, diagnóstico y reportes.
- Caché independiente de 20 segundos para Data Visualization.
- Pausa automática de consultas cuando NOC o Sala de Control están en pestañas ocultas.
- Eliminación de un refresco duplicado en la rotación de Sala de Control.
- Auditoría de apertura limitada a cargas reales, no a cada refresco cacheado.
- Invalidación inmediata después de operaciones de escritura.
- QR, accesos, acreditaciones y cupos permanecen sin caché.

## Índices RC1

Se agregó la migración `009_rc1_performance.sql` con índices para:

- accesos por evento, resultado y fecha;
- acreditaciones por evento, check-in y estado;
- cola de comunicaciones por estado y programación;
- auditoría por entidad y fecha;
- actividades por evento, estado y horario;
- captación por evento, acción y fecha.

## Caché observado

- Operación acelerada: 49,3% de aciertos con invalidación frecuente por accesos.
- Carga realista: 50% de aciertos.
- Prueba continua sin escrituras constantes: 97,6% de aciertos.
- Tamaño observado: 4 a 5 entradas, sin crecimiento descontrolado.

## Recomendaciones

- Mantener PostgreSQL para operación online seria y SQLite para demo/local.
- Ejecutar `EXPLAIN ANALYZE` en producción con datos reales antes de eventos superiores a 20.000 participantes.
- Mantener NOC/Sala de Control en 5-10 segundos y visualizaciones agregadas en 15-30 segundos.
- No reducir los TTL sin evidencia operativa.
- Incorporar caché distribuida solo cuando existan múltiples instancias.
