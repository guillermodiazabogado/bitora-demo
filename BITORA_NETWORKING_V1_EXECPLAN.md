# BITORA Networking V1 ExecPlan

## Reentry factual

- Branch inspeccionada: `chore/final-endurance-certification`.
- HEAD inspeccionado: `31d13dd`.
- Worktree inicial: limpio antes de V1.
- Stack: Python HTTP server monolitico (`server.py`), SQLite por defecto, Postgres opcional por migraciones en `backend/migrations`.
- Frontend: HTML/CSS/JS estatico en `frontend/` y espejo servido en `static/`.
- QR existente: acreditacion usa tokens `EVT-...`; Networking usa identificador publico separado `NET-...`.
- Baseline conocido antes de V1: `verificar_mvp.py` fallaba por `La inscripcion publica no genero portal`; clasificado como preexistente.

## Milestones

### M1 Foundation

Objetivo: crear dominio canonico autonomo.

Resultado: servicio `backend/services/networking.py`, migracion `027_networking_v1.sql`, tablas, taxonomia, estados, privacidad y eventos de interaccion.

Invariantes cubiertas: Person/Organization/EventParticipation separados, import no activa, PASSIVE/ACTIVE, QR publico separado.

### M2 Import/onboarding

Objetivo: importacion repetible y primer uso obligatorio.

Resultado: endpoints de preview/import, session y onboarding. Reimport conserva intencion, privacidad y contactos.

Invariantes cubiertas: import != activation, first activation requires onboarding, reimport no duplica ni destruye estado Networking.

### M3 QR/scan/contact

Objetivo: flujo participante movil.

Resultado: QR publico `NET-...`, scan idempotente, visual profile card, contactos persistentes.

Invariantes cubiertas: public QR no autentica, repeated scan no duplica, restricted channels no se exponen, no hay directorio.

### M4 External participant

Objetivo: visitantes no BITORA.

Resultado: `POST /api/networking/external-register` y `/networking-register.html`, con token privado y estado inicial `PASSIVE`.

Invariantes cubiertas: externos normalizan en el mismo modelo canonico.

### M5 UI/runbook/recovery

Objetivo: experiencia operativa y recuperable.

Resultado: `/networking.html`, `/networking-register.html`, `/networking-admin.html`, docs V1 y respaldo de evento con tablas Networking.

## Verification

Principal:

```powershell
& 'C:\Users\Noxie-PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' verificar_networking_v1.py
```

Tambien compilar:

```powershell
& 'C:\Users\Noxie-PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m py_compile server.py backend\services\networking.py backend\services\backup.py backend\database.py verificar_networking_v1.py
```

## Recovery

Los cambios son recuperables por:

- migracion SQL `backend/migrations/027_networking_v1.sql`;
- inicializacion SQLite idempotente en `NetworkingService.ensure_schema`;
- backup global SQLite/Postgres;
- backup por evento ampliado para tablas `networking_*`;
- verificador aislado con base temporal.

Rollback tecnico: eliminar rutas Networking de `server.py`, servicio `backend/services/networking.py`, migracion `027_networking_v1.sql`, paginas `networking*.html`, bloques CSS y verificador. No requiere modificar datos existentes de acreditacion.

## Known non-blocking limitations

- V1 no implementa recomendacion/matching.
- `PAUSED` y `REVOKED` estan reservados conceptualmente, pero V1 verifica `PASSIVE` y `ACTIVE`.
- Exportar a contactos del dispositivo depende del navegador/dispositivo; V1 deja canales accionables.
