# Riesgos residuales

- Docker Desktop de Windows continúa averiado; la certificación utilizó Docker Engine aislado en Ubuntu WSL.
- La tarea programada quedó registrada para el ensayo y debe retirarse cuando ya no se necesite.
- PostgreSQL aumentó su working set hasta 874,80 MiB mientras la base alcanzó 1,259 GB. No hubo degradación ni agotamiento, pero deben definirse retención, capacidad y alertas para producción.
- Vouchers, leads, vehículos y Edge todavía no forman parte de la mezcla prolongada.
- El runner con usuario interactivo no garantiza supervivencia a logout o reinicio del host; la ejecución realizada no sufrió esas interrupciones.
- No se retuvieron percentiles HTTP por ventana horaria; la tendencia temporal se evaluó mediante readiness y recursos.
- El RSS del proceso supervisor WSL no estuvo disponible; la memoria de los contenedores sí fue muestreada 720 veces.
- El muestreo cada 30 s no excluye locks transitorios entre muestras y no mide tiempos exactos de exclusión/recuperación del balanceador.
- No existen contadores por instancia que demuestren reparto equilibrado continuo del tráfico.
- No se probó un canal externo de alertas.
- Hardware, red, cámaras y operadores reales no fueron probados.
