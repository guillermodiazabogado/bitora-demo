# GO / NO-GO

- Integridad bajo carga: **GO de laboratorio**; cero pérdidas, duplicados, deadlocks u OOM en puntos frescos.
- Capacidad de inscripciones: **GO de laboratorio** para 2 instancias / 25 workers / ≥38,045 altas/s durante 120 s; mayores niveles solo ráfaga.
- Capacidad de decisiones QR: **GO observado** para 2 instancias / 8 lectores durante 120 s; 12 y 24 lectores son **NO-GO sostenido** bajo p95 ≤500 ms.
- Edge HTTP: BLOCKED.
- Software corregido: **GO local**, pendiente CI del SHA publicable.
- Producción: **NO-GO** por red/hardware, datasets grandes, Edge HTTP, sesiones masivas y staging productivo no ensayados.
