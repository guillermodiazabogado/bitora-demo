# BITORA Final Staging Certification Execution Report

Staging: https://bitora-staging.onrender.com  
Commit online: 24f891ff767c1d92bcdd7edb81c71e87caf8ab67  
Evento: BITORA E2E TEST - 10 PARTICIPANTES - E2E10-20260810-174702  
Event ID: 7

## Phase 1 - Demo Full

| Control | Resultado |
| --- | --- |
| Demo organization | BITORA TEST LAB |
| Demo event | Event 7 |
| Admin demo | PASSED |
| Producer demo | PASSED |
| Participant demo | PASSED |
| Reception demo | PASSED |
| Access demo | PASSED |
| Survey demo | PASSED |
| Certificates demo | PASSED |
| Analytics demo | PASSED |
| Demo runbook | CREATED |
| Demo Full | READY |

Evidencia:

- Participantes: 10
- Acreditados: 8
- Encuestas respondidas: 7
- Encuestas pendientes: 3
- Analytics encuesta: 70%
- Cierre asistencia definitivo: closure_id=2
- Elegibles: 8
- No elegibles: 2
- Certificados emitidos: 8
- Jobs pending/failed: 0/0
- Safe Mode: ON
- Live Mode: OFF
- Comunicaciones reales: 0

## Phase 2 - Storage

| Control | Resultado |
| --- | --- |
| Storage architecture | AUDITED |
| Persistent storage | BLOCKED BY HOSTING APPROVAL |
| Hosting plan/cost | Render Free observado en render.yaml; Persistent Disk no declarado |
| Payment executed | NO |
| Backup | BLOCKED |
| Restore isolated | BLOCKED |
| Restart persistence | BLOCKED |
| Persistence certification | BLOCKED |

Motivo: `/health` reporta `backup=missing` y `/ready` advierte que storage local requiere disco persistente y backup externo.

No se ejecuto backup/restore live porque el backup tomado sobre filesystem efimero no permite certificar persistencia ni recuperacion real.

## Phase 3 - Endurance

| Control | Resultado |
| --- | --- |
| Endurance tooling | CREATED |
| Durable runner | READY TO START LOCALLY |
| Endurance job ID | Not started in this report |
| Endurance status | NOT PASSED |
| Safe Mode | ON |
| Live Mode | OFF |
| Real communications | 0 |

Endurance historico `ENDURANCE-24H-20260810-214813`: FAILED luego de 24.13 horas.

Hallazgos:

- 1 fallo aislado del portal publico.
- 1 respuesta 502 de `/health`.
- 1 critical derivado por doble conteo del mismo 502.

Se ajusto `tools/endurance_24h_runner.py` para clasificar eventos 502/503/504 como availability events y evitar doble conteo cuando `/health` no responde. El criterio de aprobacion sigue siendo estricto y no convierte la corrida historica en PASSED.

No se inicio un nuevo Endurance porque persistent storage, backup y restore siguen bloqueados por hosting.

## Overall

Production: NOT TOUCHED  
Secrets committed: 0  
Final current state: READY FOR HOSTING APPROVAL
