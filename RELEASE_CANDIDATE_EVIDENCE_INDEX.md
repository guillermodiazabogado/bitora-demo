# RELEASE_CANDIDATE_EVIDENCE_INDEX

Commit runtime certificado: `3e82a6ae0deddf64fd77ba16fb4721b21902b9b2`

## Evidencias

| Certificacion | Estado | Evidencia | Script principal | Observaciones |
|---|---:|---|---|---|
| Security Baseline | PASSED | `BITORA_SUPERTEST_RESULTS.json` | `verificar_seguridad_basica.py` | RBAC y permisos basicos aprobados. |
| 20-Event Isolation | PASSED | `BITORA_SUPERTEST_RESULTS.json` | `verificar_multievent_isolation_20_events.py` | 20 eventos, 1.000 participantes, cruces 0. |
| Email Live | PASSED | `output/live_integrations/email_multitenant_live.json` | `verificar_email_multitenant_live.py` | Resend live con safe mode y destinatario forzado. |
| Google OAuth Live | PASSED | `output/live_integrations/google_oauth_multitenant_live.json` | `verificar_google_oauth_multitenant_live.py` | OAuth real, tokens cifrados, aislamiento aprobado. |
| WhatsApp Live | PASSED | `output/live_integrations/whatsapp_multitenant_live.json` | `verificar_whatsapp_multitenant_live.py` | Meta Cloud API, recepcion real confirmada. |
| WhatsApp Webhook Live | PASSED | `output/live_integrations/webhooks_multitenant_live.json` | `verificar_webhooks_multitenant_live.py` | Webhook real Meta, firma valida, tenant resolution. |
| Backup Multitenant Live | PASSED | `BACKUP_MULTITENANT_LIVE_CERTIFICATION_REPORT.md` | `deployment/scripts/certify_backup_restore_live.py` | PostgreSQL + storage con checksums. |
| Restore Multitenant Live | PASSED | `RESTORE_MULTITENANT_LIVE_CERTIFICATION_REPORT.md` | `deployment/scripts/certify_backup_restore_live.py` | Restore aislado, manifiestos equivalentes. |
| Disaster Recovery Live | PASSED | `DISASTER_RECOVERY_LIVE_CERTIFICATION_REPORT.md` | `deployment/scripts/certify_disaster_recovery_live.py` | Reconstruccion real, RTO/RPO medidos. |
| Upgrade From Previous Version | PASSED | `UPGRADE_FROM_PREVIOUS_VERSION_CERTIFICATION_REPORT.md` | `deployment/scripts/certify_upgrade_from_previous_live.py` | Upgrade real desde `c3ae635` a `524f138`. |
| Endurance 24h | DEFERRED | `ENDURANCE_24H_DEFERRED_PLAN.md` | Pendiente | Debe ejecutarse antes de Release estable. |

No se incluyen dumps, storage, credenciales, tokens ni logs crudos.
