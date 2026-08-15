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

## V2.3 Event Launch, Branding & Deployment Readiness

Checkpoint de arranque verificado: `fdcfb5f`.

ExecPlan aplicado:

1. Reentry y baseline
   - Verificar branch, HEAD, worktree, docs, migraciones, QR publico, admin, operaciones V2.2 y fallas heredadas.
   - Preservar `R2_RESTORE_ISOLATED_VALIDATION.json`.

2. Brand/config audit
   - Reusar `events.landing_logo_data`, `landing_primary_color` y `landing_secondary_color`.
   - Agregar solo campos event-scoped de Networking launch/brand en migracion `033`.

3. Participant branding
   - Incluir `event_branding` en payload de EventParticipation.
   - Aplicar marca en credencial, perfil publico y tokens visuales de Discovery.

4. Public URL/QR
   - Centralizar construccion de link publico por evento en `NetworkingService.public_profile_link`.
   - Validar URL publica con reglas environment-aware.
   - Mantener QR como deep link publico, no autenticacion.

5. Launch readiness
   - Agregar `NetworkingService.launch_readiness`.
   - Clasificar checks como `BLOCKING`, `WARNING` o `INFO`.
   - Integrar launch summary en operaciones V2.2.

6. Admin launch controls
   - Agregar endpoints `GET/POST /api/networking/brand` y `GET/POST /api/networking/launch`.
   - Extender `networking-admin.html` con marca, URL, launch check, launch, disable y prelaunch.

7. Public prelaunch/live behavior
   - Bloquear perfil publico antes de `LIVE`, salvo preview del owner con token privado.
   - Hacer `DISABLED` reversible y no destructivo.

8. Verification
   - Crear `verificar_networking_v2_3.py`.
   - Verificar branding default/custom, aislamiento multi-evento, public URL, prelaunch, launch, disable/re-enable, Discovery disabled, QR security, operations, backup/restore e invalid token.

Rollback/recovery:

- Revertir migracion `033`, metodos V2.3 de `NetworkingService`, endpoints brand/launch de `server.py`, bloques HTML en `networking.html`, `networking-public.html`, `networking-admin.html`, sus espejos `static/`, verifier y doc V2.3.
- La accion de launch es no destructiva; si un evento queda mal configurado, usar `POST /api/networking/launch` con `disable` o `draft` para detener acceso publico sin perder estado.

Invariantes V2.3:

- Branding es event-scoped y no altera personas/organizaciones.
- Una misma persona en dos eventos recibe marca y QR de cada EventParticipation.
- URL publica tiene una fuente autoritativa por evento.
- Produccion no debe quedar launch-ready con URL local/no HTTPS.
- Public QR no autentica owner.
- Prelaunch publico no filtra perfiles.
- Admin preview no implica launch.
- Launch/disable es reversible y no destructivo.
- Discovery puede estar deshabilitado con Networking live.
- No hay CSS/HTML arbitrario ni codigo event-specific.

## V2.4 Production Certification & Event Pilot Hardening

Checkpoint de arranque verificado: `d585a63`.

ExecPlan aplicado:

1. Reentry, baseline y fallas heredadas
   - Verificar branch, HEAD, worktree, docs V1-V2.3, migraciones hasta `033`, QR publico, auth, Discovery, operaciones, launch, backup/restore e import.
   - Preservar `R2_RESTORE_ISOLATED_VALIDATION.json`.
   - Clasificar fallas heredadas de `verificar_integridad_bitora.py` y `verificar_mvp.py`.

2. Certification harness
   - Crear `verificar_networking_v2_4.py`.
   - Cubrir QR/auth, prelaunch, launch/disable, event isolation, privacy mutation, revocation, races de scan/save/skip, reimport, external registration, exhaustion recovery, export CSV seguro, restore poblado, init idempotente y anti-directory.

3. Pilot/load runner
   - Crear `verificar_networking_pilot.py`.
   - Generar fixture deterministico con 501 EventParticipations, 500 candidatos y aproximadamente 80 organizaciones.
   - Ejecutar concurrencia acotada en credencial, perfil publico, Discovery y guardado por QR.

4. Security/QR hardening
   - Reconfirmar que public profile token `NET-*` no autentica owner.
   - Verificar perfiles publicos malformed/random/prelaunch/disabled.
   - Confirmar deep link por `NetworkingService.public_profile_link`.
   - Clasificar QR anticipado heredado como legacy accreditation/access QR, no Networking QR.

5. Concurrency/idempotency
   - Probar duplicados concurrentes de scan QR.
   - Probar convergencia QR + Discovery save en contacto canonico.
   - Probar doble skip concurrente sin historia dañina ni repeticion inmediata.
   - Documentar SQLite WAL/busy timeout y DB_LOCK de mutaciones.

6. State integrity/degradation
   - Verificar privacidad y revocacion actuales sobre historial viejo.
   - Verificar disable/re-enable de Networking no destructivo.
   - Verificar disable de Discovery preservando credencial/QR/contactos.
   - Verificar reimport live preservando contactos/historia.

7. Backup/restore/upgrade
   - Certificar backup/restore poblado sobre evento pequeño pero completo.
   - Verificar `server.init_db()` idempotente sobre DB poblada.
   - No agregar migracion V2.4; el upgrade V2.3 -> V2.4 es schema-neutral.

8. Pilot operations
   - Crear `BITORA_NETWORKING_V2_4.md`.
   - Documentar matriz manual, runbook de piloto, incident playbook, core critico y degradacion por capas.

9. Regression/certification decision
   - Ejecutar V2.4, pilot, V2.3-V1 regression, backup/auth/landing checks, py_compile y diff check.
   - Mantener manual gates separados de automated PASS.

Rollback/recovery:

- Revertir `verificar_networking_v2_4.py`, `verificar_networking_pilot.py`, doc V2.4 y el guard de CSV si se necesitara rollback.
- No hay migracion ni cambio destructivo de datos.
- La unica modificacion runtime es neutralizacion CSV de textos peligrosos para planillas; rollback no afecta estado de eventos.

Invariantes V2.4:

- Mutaciones criticas toleran retry seguro en contacto/scan/save/skip.
- Contactos canonicos no se duplican bajo concurrencia testeada.
- Privacidad/estado actual vence historial de Discovery.
- Backup/restore preserva estado operativo significativo.
- Fresh/init migration idempotente sobre DB poblada.
- QR publico Networking sigue sin autenticar owner.
- Redirect/return se mantiene en rutas internas sin redirect externo server-side.
- Certificacion distingue automated PASS y manual required.
- No se agrega AI/ML, directorio, scoring publico ni nuevo matching.

## V1.1 Event Visual Hierarchy

Checkpoint de arranque verificado: `8a05a2d`.

ExecPlan aplicado:

1. Persistir `events.networking_profile_mode` con default `AUTO`.
2. Extender sin duplicar dominio: `networking_contact_channels.scope`, `networking_organizations.activity`, `networking_organizations.specialty`.
3. Resolver jerarquia en backend mediante `profile.presentation`.
4. Renderizar scan, Mi QR y Mis contactos desde el mismo view-model.
5. Agregar configuracion en `/networking-admin.html`.
6. Verificar V1.1 y regresar V1.

Invariantes nuevas:

- La jerarquia visual nunca cambia permisos.
- `ORGANIZATION_FIRST` no muestra representante ni canales personales cuando `representative_visible=false`.
- Organizacion oculta no se muestra aunque el evento priorice organizaciones.
- Eventos distintos pueden tener modos distintos sin cambios de codigo.
