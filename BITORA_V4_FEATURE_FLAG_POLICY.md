# BITORA V4 Feature Flag Policy

## Tipos

- Plataforma: habilita capacidad global.
- Organizacion: habilita modulo para tenant.
- Evento: habilita operacion por evento.
- Experimental: pruebas controladas.
- Operativo: interruptor de seguridad o degradacion.

## Requisitos

Cada flag tiene owner, descripcion, scope, default, fecha de creacion, fecha de revision, criterio de retiro y auditoria.

## Prohibiciones

No hay flags permanentes sin propietario. No se usan flags para evitar permisos backend. No se usan flags para declarar certificaciones que no se ejecutaron.

## Fallback

Todo flag debe definir comportamiento seguro al apagarse. Si afecta comunicaciones o jobs, el fallback es pausar y auditar.

## Auditoria

Cambios de flag requieren actor, motivo, scope y timestamp.
