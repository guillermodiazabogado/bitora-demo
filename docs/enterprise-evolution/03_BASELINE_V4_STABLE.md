# BITORA V5 Discovery - Baseline V4 Stable

## Baseline Identificada

Se encontraron varias baselines documentadas. La mas relevante para V4 funcional previa es:

- BITORA_V4_FINAL_CLOSURE_REPORT.md
- BITORA_V4_FINAL_END_TO_END_REPORT.md
- BITORA_FINAL_STAGING_CERTIFICATION_EXECUTION_REPORT.md
- artifacts/endurance/ENDURANCE-R2-FULL-24H-20260814-175419/
- artifacts/endurance/ENDURANCE-RAILWAY-R2-24H-20260924-213816/ en ejecucion actual.

## Estado Documentado V4

BITORA_V4_FINAL_CLOSURE_REPORT.md declara:

- V4.1 a V4.10: PASSED.
- Full regression: PASSED.
- Security: PASSED.
- High/Critical findings: 0.
- Multitenant/multievent isolation: PASSED.
- Backup/Restore: PASSED.
- Health/smoke: PASSED.
- Endurance 24h: OMITTED en ese cierre original.

## Estado Online Actual

El entorno actual se movio a Railway:

- URL: https://web-production-7f9ac.up.railway.app
- Branch: deployment/v4-online
- HEAD local: 73a76cb55102048cb05deba8543cfc0d9f73d690
- Storage: R2 operativo segun checks previos.
- PostgreSQL: operativo segun health/ready previos.

## Endurance Actual

Run actual:

- RUN_ID: ENDURANCE-RAILWAY-R2-24H-20260924-213816
- Estado: RUNNING al momento de discovery.
- Artefactos: artifacts/endurance/ENDURANCE-RAILWAY-R2-24H-20260924-213816/
- Evidencia inicial: HEARTBEAT.json, CHECKPOINTS.jsonl, R2_CHECKS.jsonl, BACKUP_CHECKS.jsonl, FUNCTIONAL_CHECKS.jsonl.

Esta corrida NO se marca como PASSED hasta que complete 24 horas reales y pase verificacion final.

## Datos No Documentados

- CPU/memoria historica detallada: NOT DOCUMENTED.
- Throughput exacto por endpoint: NOT DOCUMENTED.
- Crecimiento de base durante endurance: NOT DOCUMENTED.
- Concurrencia exacta por terminal real: NOT DOCUMENTED.
- Logs de proveedor email entregado en Railway: NOT DOCUMENTED; actualmente hay bloqueo de Resend por dominio/remitente.

## No Regression Gate Propuesto

La baseline V4 para futuros cambios V5 debe incluir:

- verificar_v4.py;
- verificar_v4_1 a verificar_v4_10;
- seguridad basica;
- multitenant/multievent;
- backup/restore;
- storage R2;
- portal participante;
- QR/acceso;
- comunicaciones en Safe Mode;
- endurance aprobado mas reciente cuando finalice y sea verificado.
