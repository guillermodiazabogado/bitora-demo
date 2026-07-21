# Modelo De Organizaciones

## Organizacion

Representa al cliente, productora o unidad operativa que administra eventos.

Campos principales:

- nombre comercial y legal;
- contacto;
- pais, zona horaria e idioma;
- plan;
- identidad visual futura;
- safe mode email/WhatsApp;
- destinatarios forzados de prueba.

## Usuarios

`organization_users` vincula usuarios globales a organizaciones.

Roles de organizacion iniciales:

- `organization_owner`;
- `producer_admin`;
- `technical_support`;
- `event_operator`.

Los permisos operativos siguen usando la matriz actual de BITORA.
