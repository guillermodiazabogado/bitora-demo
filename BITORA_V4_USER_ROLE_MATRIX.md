# BITORA V4 User Role Matrix

## Principios

Rol, permiso, scope y condicion son conceptos separados. Todo permiso debe validarse en backend y auditar acciones sensibles. Un usuario puede pertenecer a multiples organizaciones y eventos, pero cada accion se resuelve contra el scope activo.

| Perfil | Objetivo | Puede | No Puede | Datos Visibles | Scope | Riesgo |
|---|---|---|---|---|---|---|
| Superusuario | Administrar plataforma | Configurar organizaciones, auditoria global, soporte critico | Operar sin auditoria | Global, sanitizado donde corresponda | Plataforma | Alto |
| Administrador organizacion | Gobernar tenant | Usuarios, integraciones, eventos, permisos | Acceder a otra organizacion | Organizacion completa | Organizacion | Alto |
| Productor | Preparar evento | Configuracion, participantes, cupos, reportes | Cambiar integraciones globales sin permiso | Eventos asignados | Evento | Alto |
| Coordinador evento | Operar agenda | Actividades, salas, incidencias, asistencia | Gestionar usuarios globales | Evento y jornada | Evento | Medio |
| Operador | Ejecutar tareas | Registrar, buscar, resolver incidencias asignadas | Configurar permisos | Datos operativos necesarios | Evento/zona | Medio |
| Recepcion | Acreditar | Buscar participantes, acreditar, corregir con motivo | Ver auditoria completa o integraciones | Participantes del evento | Evento | Medio |
| Control acceso | Validar ingreso | Escanear QR, ver resultado y razon | Editar participante | QR y permiso de acceso | Evento/zona | Medio |
| Disertante | Completar perfil | Editar perfil propio, materiales, disponibilidad | Ver participantes completos salvo permiso | Propio y actividades asignadas | Persona/actividad | Bajo |
| Participante | Gestionar asistencia | Portal propio, reservas, certificado propio | Ver datos ajenos | Datos propios | Participante | Bajo |
| Visualizador | Consultar | Reportes permitidos | Modificar acreditaciones o permisos | Lectura filtrada | Evento/org | Medio |
| Auditor | Verificar | Auditoria, evidencia, reportes | Ejecutar acciones operativas | Logs sanitizados | Org/plataforma | Alto |

## Multiples Organizaciones y Eventos

La sesion debe exponer un contexto activo. Cambiar de contexto no otorga permisos; solo cambia el scope sobre el cual se evaluan permisos existentes.

## Permisos Temporales y Delegados

Todo permiso temporal debe tener emisor, receptor, motivo, alcance, fecha de inicio, fecha de fin y revocacion. Las delegaciones vencidas o revocadas no deben conservar acceso por cache.

## Perdida de Permisos y Usuarios Desactivados

La perdida de permisos debe invalidar acciones nuevas y sesiones operativas sensibles. Usuarios desactivados no pueden operar ni consumir tokens internos. La auditoria historica se conserva.

## Colaboradores Externos

Se asignan con scope minimo, fecha de vencimiento y sin acceso a datos personales completos salvo permiso explicito.
