# BITORA Staging Stability Root Cause Report

Fecha: 2026-08-11  
Staging: https://bitora-staging.onrender.com  
Endurance auditado: ENDURANCE-24H-20260810-214813  
Resultado historico: FAILED

## Resumen

La corrida de 24.13 horas ejecuto 95 iteraciones y fallo con:

- Critical findings: 2
- High findings: 1
- Safe Mode: ON
- Live Mode: OFF
- Comunicaciones reales: 0

No hay evidencia de corrupcion, perdida de datos, cruce multi-tenant, jobs acumulados ni envios reales.

## Incidente 1

| Campo | Valor |
| --- | --- |
| Timestamp UTC | 2026-08-11T01:55:14+00:00 |
| Sintoma | Portal publico con timeout/fallo de fixture |
| Severidad historica | HIGH |
| Duracion observada | Aislada; siguiente checkpoint OK |
| DB | Sin evidencia de falla |
| Jobs | 0 pending / 0 failed |
| Safe Mode | ON |
| Root cause | No confirmada |
| Hipotesis principal | Latencia transitoria de plataforma, red o arranque |
| Confianza | Media-baja |

## Incidente 2

| Campo | Valor |
| --- | --- |
| Timestamp UTC | 2026-08-11T13:43:26+00:00 |
| Sintoma | `/health` respondio 502 Bad Gateway |
| Severidad historica | CRITICAL + CRITICAL derivado |
| Duracion observada | Aislada; siguiente checkpoint OK |
| DB | Sin evidencia de falla persistente |
| Portal/ready | Sin evidencia de degradacion sostenida |
| Root cause | No confirmada |
| Hipotesis principal | Evento transitorio de Render: cold start, restart, edge/proxy o disponibilidad corta |
| Confianza | Media |

## Observacion de tooling

La herramienta historica contabilizo el 502 como dos critical findings:

1. `health.unavailable`
2. `health.status = None`

Se ajusto `tools/endurance_24h_runner.py` para evitar doble conteo cuando `/health` no responde y para clasificar 502/503/504 como `AVAILABILITY` en la proxima corrida. El criterio de certificacion sigue siendo estricto: una corrida final no debe aprobar con eventos de disponibilidad no explicados.

## Estado actual del staging

`/health` responde `ok`, PostgreSQL online y jobs en cero.  
`/ready` responde `ready`, con warning de storage persistente pendiente.

## Conclusiones

El Endurance anterior fue real y debe conservarse como FAILED.

No corresponde iniciar una nueva corrida de 24 horas hasta resolver:

1. persistencia real de storage/backups;
2. decision de hosting;
3. burn-in previo sin fallos;
4. evidencia de estabilidad suficiente.
