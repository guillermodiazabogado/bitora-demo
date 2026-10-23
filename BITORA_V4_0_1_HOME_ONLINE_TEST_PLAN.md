# BITORA V4.0.1 Home Visual - Online Staging Test Plan

## Objetivo

Validar en `https://bitora-staging.onrender.com` que la Home Visual de Productor desplegada desde `deployment/v4-online` reproduce el comportamiento aprobado localmente en `develop/v4`.

## Alcance

- Login sin usuario precargado.
- Productor con Home Visual inicial.
- Productor con barra superior original reducida a `Inicio`.
- Tarjetas de módulos habilitadas por permisos reales.
- Navegación hacia módulos existentes.
- Retorno al Home.
- Validación de roles no Productor.
- Responsive desktop, tablet y mobile.
- Safe Mode activo.
- Live Mode desactivado.

## Casos Críticos

1. Login online responde y no tiene usuario seleccionado por defecto.
2. `/health` responde `status=ok` y `env=staging`.
3. `/ready` responde `status=ready`.
4. PostgreSQL está activo.
5. Safe Mode está activo.
6. Live Mode está desactivado.
7. Productor inicia en Home Visual.
8. Productor ve exactamente 12 tarjetas.
9. Productor ve solo `Inicio` en la barra superior original.
10. Cada tarjeta abre su módulo.
11. Cada módulo permite volver al Home sin perder sesión ni evento.
12. Productor limitado ve solo tarjetas autorizadas.
13. Usuario no Productor no recibe Home específica de Productor.
14. URL directa a módulo prohibido queda bloqueada por backend.
15. No hay comunicaciones no autorizadas.
16. No hay secretos expuestos.

## Resultado Esperado

`HOME VISUAL V4.0.1 - ONLINE STAGING VALIDATED`

## Fuera de Alcance

- Persistent Disk.
- PR #12.
- Endurance 24h.
- Producción.
- Nuevas funcionalidades.
