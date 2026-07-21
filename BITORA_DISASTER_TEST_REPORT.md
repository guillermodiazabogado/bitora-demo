# BITORA Disaster Test Report

- PASSED `integrations_disaster_recovery`: {"name": "integrations_disaster_recovery", "mode": "contract", "status": "omitted", "missing_env": ["APP_ENV", "QR_POSTGRES_DSN", "BDF_WORKER_LIVE"], "checks": {"jobs_persisted": true, "jobs_keep_organization": true, "lost_jobs": 0, "duplicate_messages": 0}}

- OMITTED `disaster_recovery_live`: Pendiente perfil --disaster en staging destructible.
