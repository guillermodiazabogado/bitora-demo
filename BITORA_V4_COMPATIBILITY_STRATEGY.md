# BITORA V4 Compatibility Strategy

## Objetivo

Permitir que V4 conviva con la Release Candidate sin romper datos, rutas, jobs, storage ni certificaciones heredadas.

## Estrategia

- Cambios aditivos primero.
- Feature flags por modulo.
- Migraciones progresivas con defaults seguros.
- Backfills idempotentes.
- Rutas legacy conservadas como contrato operativo.
- Nuevas APIs versionadas cuando sea necesario.

## Datos Existentes

Toda nueva entidad debe poder inicializarse desde datos actuales o quedar vacia con estado seguro. No se debe requerir carga manual masiva para que la app arranque.

## Jobs Antiguos

Jobs existentes conservan contrato. Nuevos jobs deben incluir organization_id, event_id, integration_id cuando corresponda e idempotency key.

## Storage

Nuevas rutas bajo scope de organizacion/evento. No mover archivos existentes sin migracion reversible o backup previo.

## Rollback

Preferir rollback de aplicacion cuando cambios sean aditivos. Para migraciones no reversibles, la politica es restore certificado.

## Feature Rollout

Cada modulo V4 arranca deshabilitado por defecto fuera de entornos de prueba, se habilita por organizacion/evento y se recertifica segun matriz.
