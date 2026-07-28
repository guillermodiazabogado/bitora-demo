# UPGRADE_FROM_PREVIOUS_VERSION_CERTIFICATION_REPORT

Resultado: PASSED

Run ID: UPGRADE-LIVE-20260728-190438

Version origen:

```text
c3ae63585c53105c2e99912148df0be8ae803afb
```

Version destino:

```text
524f13890c1df02e095077f9fc58204042b1682d
```

Resultados:

```text
Previous version selection: PASSED
Previous version installation: PASSED
Previous version dataset: PASSED
Pre-upgrade manifest: PASSED
Pre-upgrade backup: PASSED
Upgrade precheck: PASSED
Upgrade execution: PASSED
Database migrations: PASSED
Migration idempotency: PASSED
Data integrity: PASSED
Storage integrity: PASSED
Sequence integrity: PASSED
Functional validation: PASSED
Multitenant isolation: PASSED
Jobs compatibility: PASSED
External effects: 0
Duplicate jobs: 0
Duplicate sends: 0
Missing records: 0
Corrupted files: 0
Cross-event access: 0
Cross-organization access: 0
Failed upgrade recovery: PASSED
Secrets exposed: 0
```

Metricas:

```text
Precheck seconds: 32.371
Pre-upgrade backup seconds: 0.852
Upgrade seconds: 31.723
Total seconds: 76.04
```

Gate:

```text
upgrade_from_previous_version: PASSED
```
