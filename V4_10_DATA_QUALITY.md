# BITORA V4.10 Data Quality

Data quality detecta, sin modificar datos:

- participantes sin email;
- tokens QR duplicados;
- reservas huerfanas;
- reservas vinculadas a actividades de otro evento;
- snapshots obsoletos.

Severidades:

- INFO
- WARNING
- ERROR
- BLOCKING

Los hallazgos se registran en `analytics_v4_data_quality_issues`.
