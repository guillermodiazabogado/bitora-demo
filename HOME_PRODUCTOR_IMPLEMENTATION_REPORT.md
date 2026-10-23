# Home Visual de Productor

Fecha: 2026-08-04

Rama: `deployment/v4-online`

## Objetivo

Implementar una pantalla inicial tipo Home visual para el rol efectivo `Productor`, con tarjetas de acceso rapido a los modulos habilitados para el usuario en el evento activo.

## Alcance implementado

- Nueva vista frontend `home`.
- Boton `Inicio` en la navegacion principal.
- Home visual con selector de evento activo.
- Catalogo de tarjetas de modulos:
  - Panel de Control
  - Inscripciones
  - Recepcion
  - Acceso
  - Asistencia
  - Actividades
  - Speakers
  - Certificados
  - Encuestas
  - Comunicaciones
  - Operations Center
  - Analytics
- Filtro de tarjetas por permisos reales del frontend:
  - `canSeeModule(...)`
  - `canDo(...)`
  - feature flags del evento cuando aplica.
- Redireccion a vistas SPA existentes o paginas V4 existentes.
- Estado inferior de Safe Mode, envios en vivo, entorno y ultima actualizacion.
- Responsive para desktop, tablet y mobile.

## Seguridad y permisos

No se agrego un permiso backend nuevo para la Home.

La Home solo se muestra cuando:

- existe evento activo;
- el rol efectivo es `Productor`;
- el usuario puede ver `dashboard`.

Cada tarjeta vuelve a validar permisos antes de abrir el modulo. Los endpoints backend siguen siendo la fuente de seguridad efectiva.

## Archivos modificados

- `frontend/index.html`
- `frontend/app.js`
- `frontend/styles.css`
- `static/index.html`
- `static/app.js`
- `static/styles.css`
- `verificar_home_productor.py`

## Validaciones ejecutadas

- `node --check frontend/app.js`: PASSED
- `node --check static/app.js`: PASSED
- `python verificar_home_productor.py`: PASSED
- `python -m py_compile verificar_home_productor.py server.py backend/app.py`: PASSED
- Smoke local temporal con login `Productor`: PASSED
- API permisos Productor con evento activo: PASSED
- HTML autenticado contiene Home visual: PASSED
- Servidor temporal detenido al finalizar: PASSED

## Restricciones respetadas

- No se modifico la arquitectura.
- No se cambiaron permisos backend existentes.
- No se eliminaron modulos.
- No se elimino el menu actual.
- No se activaron integraciones live.
- No se ejecuto Endurance.
- No se declaro release estable.
