# BITORA Multi-Tenant - Estado Actual

BITORA queda preparado para operar con multiples organizaciones dentro de una misma instalacion, manteniendo compatibilidad con los eventos existentes.

## Estado implementado

- Organizacion inicial automatica: `BITORA Principal`.
- Los eventos existentes se asignan automaticamente a la organizacion inicial.
- Los usuarios existentes se vinculan a la organizacion inicial.
- Cada evento tiene `organization_id`.
- Existen integraciones por organizacion.
- Existen asignaciones de integraciones por evento y canal.
- La cola de comunicaciones guarda `organization_id` e `integration_id`.
- Los secretos de integraciones se cifran con `BITORA_INTEGRATION_ENCRYPTION_KEY`.
- Las respuestas API no exponen secretos.
- Safe mode puede resolverse por organizacion.
- La matriz de permisos incorpora organizaciones e integraciones.

## Restricciones actuales

- Google OAuth real queda preparado a nivel de modelo, pendiente de credenciales y pantalla final de autorizacion.
- Meta/WhatsApp por organizacion queda preparado a nivel de modelo, pendiente de flujo OAuth y prueba live.
- Email por organizacion queda preparado a nivel de modelo, pendiente de prueba live con dominio/remitente por organizacion.
- Backup/restauracion multiorganizacion completo queda pendiente de validacion live.

## Decision

Multi-tenant queda aprobado con restricciones para seguir desarrollando sobre esta base.
