# Arquitectura De Integraciones

## Alcance

Las integraciones pasan a vivir en la organizacion y se asignan por evento/canal.

## Tipos iniciales

- `email_provider`;
- `whatsapp_provider`;
- `calendar_provider`;
- `storage_provider`;
- `analytics_provider`;
- `payment_provider` preparado para futuro.

## Modos

- `platform_managed`: BITORA administra el proveedor.
- `client_owned`: la organizacion aporta sus credenciales.
- `demo`: sin envio real.
- `disabled`: desactivada.

## Seguridad

Los secretos se guardan cifrados en `configuration_encrypted`. Las respuestas usan metadata sanitizada.
