# BITORA V4.0.1 - Producer Visual Home

Fecha: 2026-08-04

Rama: `feature/v4.0.1-producer-visual-home`

Base: `develop/v4`

## Objetivo

Implementar una Home visual para el perfil Productor. Al iniciar sesion, cuando el usuario tiene rol efectivo `Productor` y un evento activo, BITORA muestra un tablero de tarjetas con acceso rapido a los modulos habilitados para ese usuario en ese evento.

## Arquitectura

La Home es una vista frontend adicional llamada `home`.

No agrega permisos backend nuevos. No modifica la matriz de permisos existente. No cambia endpoints ni reglas de autorizacion.

La seguridad sigue funcionando en dos niveles:

- frontend: la Home solo renderiza tarjetas habilitadas por `canSeeModule(...)`, `canDo(...)` y feature flags del evento;
- backend: cada modulo y endpoint conserva sus validaciones actuales de permisos, evento y organizacion.

## Funcionamiento

La vista aparece solamente cuando se cumplen estas condiciones:

- existe un evento activo;
- el rol efectivo del usuario es `Productor`;
- el usuario tiene permiso para ver `dashboard`.

Si el Productor tiene un unico evento activo y no se solicito otra vista, BITORA abre la Home visual por defecto.

El menu tradicional permanece disponible. El boton `Inicio` permite volver a esta Home desde cualquier modulo.

## Catalogo de tarjetas

Las tarjetas implementadas son:

| Clave | Titulo | Destino |
| --- | --- | --- |
| `dashboard` | Panel de Control | Vista SPA `dashboard` |
| `register` | Inscripciones | Vista SPA `register` |
| `reception` | Recepcion | Vista SPA `reception` |
| `access` | Acceso | Vista SPA `access` |
| `attendance` | Asistencia | `/attendance-closure.html` |
| `agenda` | Actividades | Vista SPA `agenda` |
| `speakers` | Speakers | `/speakers-v4.html` |
| `certificates` | Certificados | `/certificates-v4.html` |
| `surveys` | Encuestas | `/surveys-v4.html` |
| `communications` | Comunicaciones | Vista SPA `communications` |
| `operations` | Operations Center | `/operations-center-v4.html` |
| `analytics` | Analytics | `/analytics-v4.html` |

Cada tarjeta muestra:

- icono textual compacto;
- titulo;
- descripcion corta;
- metrica o estado contextual cuando esta disponible;
- indicador de apertura.

## Selector de evento

La Home incorpora un selector de evento sincronizado con el selector principal de BITORA. Al cambiar el evento:

- se actualiza el evento activo global;
- se recargan permisos;
- se recalculan las tarjetas visibles;
- se mantienen las reglas de acceso existentes.

## Responsive

El layout usa:

- 3 columnas en desktop;
- 2 columnas en tablet;
- 1 columna en mobile.

El panel lateral se adapta a una disposicion superior en pantallas chicas. No se usan dependencias visuales nuevas.

## Permisos

La Home no expone modulos sin permiso.

Filtros aplicados:

- `canSeeModule(module)` para modulos SPA;
- `canSeeModule(permissionModule)` para paginas V4 asociadas a modulos;
- `canDo(action)` para accesos controlados por permiso fino;
- feature flags del evento para agenda, acceso, recepcion e inscripciones.

No se permite abrir una tarjeta si el modulo ya no esta permitido al momento del click.

## Navegacion

La navegacion respeta los destinos existentes:

- vistas SPA con `setView(...)`;
- paginas V4 con `event_id` en query string;
- menu superior tradicional sin cambios funcionales.

El boton `Inicio` se oculta si el usuario no es Productor o si no hay evento activo.

## Restricciones

No se modifico:

- Render;
- Docker;
- PostgreSQL;
- deployment;
- backup;
- restore;
- Meta;
- WhatsApp;
- Cloudflare;
- Endurance;
- permisos backend;
- arquitectura funcional.

## Pruebas ejecutadas

- `node --check frontend/app.js`: PASSED
- `node --check static/app.js`: PASSED
- `python verificar_home_productor.py`: PASSED
- `python -m py_compile verificar_home_productor.py server.py backend/app.py`: PASSED
- Secret scan: PASSED
- Smoke local temporal con login `Productor`: PASSED
- Productor con evento activo: PASSED
- Productor con permisos de modulos: PASSED
- Usuario no Productor: protegido por guard `effectiveRole() === "Productor"`
- Sin evento activo: Home no disponible
- Menu tradicional: conservado
- Boton Inicio: implementado
- Responsive desktop/tablet/mobile: cubierto por CSS dedicado

## Referencia visual

La implementacion sigue la referencia provista para un dashboard de modulos de Productor con:

- panel lateral oscuro;
- grilla de tarjetas;
- selector de evento activo;
- tarjetas con color por modulo;
- estado inferior de entorno y modo seguro.

No se incorporo la imagen al repositorio para evitar activos innecesarios.
