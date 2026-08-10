# BITORA Test Users Guide

Esta guia documenta perfiles de prueba locales para validar BITORA sin publicar contrasenas, hashes, tokens ni secretos.

Las contrasenas temporales se generan localmente y se muestran una sola vez en consola. No forman parte del repositorio.

## Politica

- Usar estos usuarios solo en entornos locales o de prueba explicitos.
- No crear automaticamente estos usuarios en staging productivo ni produccion.
- No usar claves demo inseguras como `1234`, `2222` o `3333`.
- No guardar contrasenas en Git, reportes, logs persistentes ni PRs.
- Regenerar las contrasenas antes de cada sesion de prueba compartida.

## Evento De Prueba

- Organizacion: organizacion de prueba local de BITORA.
- Evento: `Evento Demo Home Productor V4.0.1`.
- Alcance: validacion de UX, navegacion, permisos visibles y convivencia de modulos.

## Perfiles

| Perfil | Usuario demo | Rol efectivo | Evento | Modulos visibles esperados |
| --- | --- | --- | --- | --- |
| Super Admin | `superadmin-demo` | Super Admin | Evento Demo Home Productor V4.0.1 | Todos los modulos administrativos y operativos autorizados |
| Productor | `productor-demo` | Productor | Evento Demo Home Productor V4.0.1 | Home Visual, Panel, Inscripciones, Recepcion, Acceso, Asistencia, Actividades, Speakers, Certificados, Encuestas, Comunicaciones, Operations Center, Analytics |
| Coordinador | `coordinador-demo` | Coordinador | Evento Demo Home Productor V4.0.1 | Modulos operativos permitidos por RBAC vigente |
| Recepcion | `recepcion-demo` | Operador de recepcion | Evento Demo Home Productor V4.0.1 | Recepcion y modulos permitidos por RBAC vigente |
| Acceso | `acceso-demo` | Operador de acceso | Evento Demo Home Productor V4.0.1 | Acceso y modulos permitidos por RBAC vigente |
| Visualizador | `visualizador-demo` | Visualizador | Evento Demo Home Productor V4.0.1 | Lectura limitada segun RBAC vigente |
| Comunicaciones | `comunicaciones-demo` | Comunicaciones | Evento Demo Home Productor V4.0.1 | Comunicaciones permitidas por RBAC vigente |
| Soporte | `soporte-demo` | Soporte tecnico | Evento Demo Home Productor V4.0.1 | Diagnostico tecnico permitido por RBAC vigente |

## Regeneracion De Contrasenas

Para una prueba local, generar una contrasena aleatoria independiente por usuario con al menos 14 caracteres y actualizarla usando el mecanismo real de usuarios de BITORA o un script de preparacion local que use el hash de PIN del servidor.

La salida de credenciales debe mostrarse una sola vez en consola local y no debe persistirse.

## Seguridad

La Home Visual de Productor no concede permisos. El backend sigue siendo la fuente de verdad para autorizacion, ownership de organizacion, ownership de evento y acceso directo a rutas protegidas.
