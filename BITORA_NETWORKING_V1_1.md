# BITORA Networking V1.1 - Event Visual Hierarchy

## Estado factual

- Punto de partida verificado: `8a05a2d - feat: add BITORA Networking V1`.
- Rama de inicio: `chore/final-endurance-certification`.
- Arbol de trabajo al inicio: limpio.
- Baseline heredado confirmado: `verificar_mvp.py` sigue fallando con `La inscripcion publica no genero portal`.

## Objetivo

V1.1 agrega jerarquia visual configurable por evento sin cambiar el dominio canonico:

- `ORGANIZATION_FIRST`
- `PERSON_FIRST`
- `AUTO`

El modo cambia la presentacion, no la autorizacion ni la privacidad.

## Arquitectura elegida

- Configuracion por evento: `events.networking_profile_mode`.
- Extension minima de organizacion: `networking_organizations.activity` y `networking_organizations.specialty`.
- Extension minima de canales: `networking_contact_channels.scope` con `PERSONAL` u `ORGANIZATION`.
- Resolver backend unico: cada perfil conserva el payload V1 y suma `presentation`.

El frontend renderiza `profile.presentation`; no decide permisos ni jerarquia por su cuenta.

## Modos

### Organization First

Prioriza:

- logo/nombre de organizacion;
- actividad/sector y especialidad;
- descripcion/oferta;
- canales corporativos permitidos;
- representante como informacion secundaria solo si es visible.

Si no hay organizacion visible, degrada a `PERSON_FIRST`.

### Person First

Prioriza:

- persona/foto;
- rol/cargo;
- organizacion como contexto secundario;
- canales personales permitidos.

### AUTO

Fallback deterministico actual: `PERSON_FIRST`.

## Privacidad

La jerarquia visual no otorga acceso.

- Canales `HIDDEN` nunca se muestran.
- Si `representative_visible=false`, no se muestran nombre, rol, foto, funcion ni canales personales.
- Si la organizacion esta oculta, no se muestra como entidad primaria aunque el evento sea `ORGANIZATION_FIRST`.
- La oportunidad de organizacion puede seguir visible y accionable si la organizacion y sus canales corporativos estan permitidos.

## Configuracion manual

Desde UI:

- abrir `/networking-admin.html`;
- cargar el `event_id`;
- elegir `Organizacion primero`, `Persona primero` o `Automatico/default`;
- guardar.

Via API:

```json
POST /api/networking/config
{
  "actor": "Admin",
  "event_id": 1,
  "networking_profile_mode": "ORGANIZATION_FIRST"
}
```

Leer config:

```text
GET /api/networking/config?actor=Admin&event_id=1
```

## Importacion V1.1

Campos nuevos opcionales:

- `organization_activity` / `activity` / `actividad` / `sector`
- `organization_specialty` / `specialty` / `especialidad`
- `channels[].scope`: `PERSONAL` o `ORGANIZATION`

Ejemplo:

```json
{
  "first_name": "Bruno",
  "last_name": "Representante",
  "email": "bruno@example.test",
  "organization": "Hormigon Patagonia",
  "organization_activity": "Construccion",
  "organization_specialty": "Materiales",
  "organization_description": "Proveedor regional de soluciones para obras.",
  "channels": [
    {"type": "website", "value": "https://hormigon.example", "visibility": "PUBLIC", "scope": "ORGANIZATION"},
    {"type": "email", "value": "bruno@example.test", "visibility": "HIDDEN", "scope": "PERSONAL"}
  ]
}
```

La reimportacion sigue siendo segura: actualiza datos source-owned y preserva contactos, intencion y privacidad.

## Verificacion

Principal:

```powershell
& 'C:\Users\Noxie-PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' verificar_networking_v1_1.py
```

Regresion V1:

```powershell
& 'C:\Users\Noxie-PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' verificar_networking_v1.py
```

Checks relacionados:

```powershell
& 'C:\Users\Noxie-PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' verificar_event_restore.py
& 'C:\Users\Noxie-PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' verificar_backup_restore.py
& 'C:\Users\Noxie-PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' verificar_auth_red.py
```
