# BITORA V4.10 Backup Restore Report

Tablas V4.10 incluidas en backup por evento:

- analytics snapshots;
- analytics reports;
- analytics export jobs;
- saved views;
- data quality issues;
- functional closure reviews;
- closure gate results;
- findings;
- actions.

Politica post-restore:

- snapshots: `STALE`;
- reportes: `RESTORED_REVIEW`;
- export jobs: `RESTORED_EXPIRED`;
- closure reviews: `RESTORED_REVIEW`;
- closure actions: `RESTORED_PENDING_REVIEW`.

Verificador:

- backup y restore V4.10: PASSED.
