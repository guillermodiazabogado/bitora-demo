# BITORA Multi-Tenant Architecture

## Principio

Un unico BITORA puede alojar varias organizaciones. Cada organizacion administra sus eventos, usuarios asignados e integraciones propias.

## Entidades

- `organizations`: clientes/productoras/owners.
- `organization_users`: usuarios vinculados a organizaciones.
- `events.organization_id`: pertenencia estricta de cada evento.
- `organization_integrations`: proveedores configurados por organizacion.
- `event_integrations`: seleccion de proveedor por evento y canal.
- `communication_queue.organization_id`: trazabilidad tenant de cada comunicacion.
- `communication_queue.integration_id`: proveedor asignado al envio.

## Reglas

- Un usuario puede estar en varias organizaciones.
- Un evento pertenece a una sola organizacion.
- Una integracion solo puede asignarse a eventos de su misma organizacion.
- Los secretos nunca se devuelven por API.
- El Super Admin conserva acceso total.

## Compatibilidad

Los eventos previos migran a `BITORA Principal`, por lo que la experiencia existente no cambia.
