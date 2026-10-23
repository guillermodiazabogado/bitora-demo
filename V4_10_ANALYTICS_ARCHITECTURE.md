# BITORA V4.10 Analytics Architecture

La arquitectura elegida es proporcional al sistema actual:

- consultas directas explicables sobre tablas fuente;
- snapshots versionados y reconstruibles para evidencia;
- reportes derivados de snapshots;
- exportaciones auditadas;
- data quality no destructivo;
- feature flag `analytics_v4_enabled`.

Analytics no es fuente primaria. Las tablas V4.10 preservan evidencia y resultados derivados, pero las metricas se pueden reconstruir desde los dominios originales.

Tablas nuevas:

- `analytics_v4_snapshots`
- `analytics_v4_reports`
- `analytics_v4_export_jobs`
- `analytics_v4_saved_views`
- `analytics_v4_data_quality_issues`
- `functional_closure_reviews`
- `functional_closure_gate_results`
- `functional_closure_findings`
- `functional_closure_actions`
