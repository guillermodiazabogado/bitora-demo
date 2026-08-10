# BITORA User Management Guide

Estado: USER MANAGEMENT V4

## Alcance

BITORA permite administrar usuarios desde el panel `Usuarios y Permisos`.

Acciones disponibles:

- crear usuario;
- seleccionar rol real del sistema;
- asignar usuario a un evento;
- restablecer contraseña;
- generar contraseña temporal;
- forzar cambio de contraseña al ingresar;
- activar o desactivar usuario;
- consultar estado operativo;
- auditar cambios.

## Roles Reales

- Super Admin
- Productor
- Coordinador
- Operador de recepcion
- Operador de acceso
- Visualizador
- Comunicaciones
- Soporte tecnico

## Seguridad

- Las contraseñas nunca se guardan en texto plano.
- Las respuestas de `/api/users` no exponen `pin_hash`.
- Los resets quedan auditados.
- Las contraseñas temporales generadas se muestran una sola vez en la respuesta del panel.
- Un usuario con `must_change_password` debe cambiar su contraseña antes de operar la aplicacion.
- Un administrador no puede desactivarse a si mismo desde la accion de estado.

## Politica de Contraseña

Minimo requerido:

- 10 caracteres;
- una mayuscula;
- una minuscula;
- un numero;
- un simbolo.

## Bootstrap Local/Staging

Para crear usuarios de prueba se usa:

```bash
python scripts/bootstrap_test_users.py --reset
```

El script:

- rechaza `APP_ENV=production`;
- usa usuarios y roles de prueba;
- asigna organizacion y evento existente;
- genera contraseñas temporales;
- muestra las contraseñas solo en consola;
- no escribe secretos en archivos ni reportes.

## Auditoria

Eventos auditados:

- `user.saved`
- `user.password_reset`
- `user.password_changed`
- `user.activated`
- `user.deactivated`
- `user.bootstrap_test`

## Limitaciones

- La creacion de usuarios globales queda restringida a `Super Admin`.
- La asignacion de equipo por evento sigue usando permisos de configuracion del evento.
- Este documento no contiene contraseñas ni secretos.
