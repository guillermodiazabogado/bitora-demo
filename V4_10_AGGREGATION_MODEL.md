# BITORA V4.10 Aggregation Model

Modelo:

- agregacion on-demand por evento;
- filtros sanitizados;
- snapshots con hash deterministico;
- reportes referenciando snapshots;
- data quality registrada como hallazgo, sin modificar datos.

Despues de restore:

- snapshots quedan `STALE`;
- reportes quedan `RESTORED_REVIEW`;
- cierres funcionales quedan `RESTORED_REVIEW`;
- exportaciones quedan `RESTORED_EXPIRED`.
