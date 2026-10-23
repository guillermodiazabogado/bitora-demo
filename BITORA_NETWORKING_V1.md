# BITORA Networking V1

## Estado

V1 implementado como modulo autonomo sobre el repositorio actual. El intercambio inicial es por importacion de filas/API y formulario publico; no depende de sincronizacion viva con BITORA.

Verificacion principal:

```powershell
& 'C:\Users\Noxie-PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' verificar_networking_v1.py
```

Resultado esperado:

```text
OK: BITORA Networking V1 import/onboarding/QR/scan/contact/privacy/external
```

## Arquitectura

El dominio separa identidad permanente de comportamiento por evento:

- `people`: persona canonica existente.
- `networking_organizations`: organizacion canonica de Networking.
- `networking_event_participations`: participacion de una persona en un evento especifico.
- `networking_intents`: modo, direccion, apertura, bio, offers/seeks/intereses y visibilidad declarada.
- `networking_contact_channels`: canales extensibles con visibilidad por canal.
- `networking_taxonomy_concepts` y `networking_classifications`: base semantica para futura relevancia, sin matching V1.
- `networking_contacts`: contactos creados por escaneo, idempotentes.
- `networking_interaction_events`: historial operativo de import, onboarding y scan.

El QR publico de Networking contiene un identificador `NET-...` y no autentica al propietario. El acceso privado usa token de acreditacion BITORA existente o token privado emitido al registro externo.

## Estados

- Importacion crea participantes `PASSIVE`.
- Primer uso/onboarding cambia a `ACTIVE`.
- V1 distingue correctamente `PASSIVE` vs `ACTIVE`.
- `PAUSED` y `REVOKED` quedan reservados por el modelo para evolucion posterior.

## Endpoints

Admin:

- `POST /api/networking/import/preview`
- `POST /api/networking/import`

Participante/publico:

- `POST /api/networking/external-register`
- `GET /api/networking/session?token=...&event_id=...`
- `POST /api/networking/onboarding`
- `GET /api/networking/qr.svg?profile_id=NET-...`
- `POST /api/networking/scan`
- `GET /api/networking/contacts?token=...`
- `GET /api/networking/profile?profile_id=NET-...&token=...`

Pantallas:

- `/networking.html`: experiencia participante movil.
- `/networking-register.html?event_id=...`: formulario publico por evento.
- `/networking-admin.html`: importacion/validacion operativa.

## Importacion

Ejemplo minimo:

```json
[
  {
    "source_external_id": "bitora-001",
    "first_name": "Ana",
    "last_name": "Demo",
    "email": "ana@example.test",
    "organization": "Expo Connect",
    "title": "Directora Comercial",
    "function": "COMMERCIAL",
    "seniority": "MANAGEMENT",
    "linkedin": "https://linkedin.example/ana",
    "website": "https://ana.example"
  }
]
```

La reimportacion es segura: no duplica participaciones, no borra contactos y no pisa intencion/privacidad declarada en Networking.

## Registro externo

El formulario publico crea la misma arquitectura canonica que un import:

`Person + Organization + EventParticipation(PASSIVE) + ContactChannels`

El usuario externo recibe un token privado y debe completar onboarding para pasar a `ACTIVE`.

## Privacidad

La visibilidad opera por canal:

- `PUBLIC`
- `CONTACTS`
- `HIDDEN`

Un canal `HIDDEN` no se expone en perfil publico, scan ni contactos. La oportunidad de organizacion puede seguir visible aunque el representante o sus canales esten restringidos.

## Fuera de alcance V1

No se implementa directorio, feed de recomendaciones, scoring, swipes, match bilateral, chat, agenda de reuniones, embeddings, ML ni sincronizacion API viva con BITORA.
