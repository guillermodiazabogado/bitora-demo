# BITORA Engineering Execution Standard

## Alcance

Este estandar aplica a todo sprint funcional de BITORA. Su objetivo es mantener cambios incrementales, auditables y compatibles con la arquitectura multi-tenant existente.

## Ramas, commits y PR

- Cada version funcional se implementa en una rama propia desde `develop/v4`.
- No se mezclan versiones en una misma rama.
- Cada rama termina con commit, push, PR, review controlado y merge a `develop/v4`.
- No se usa force push sobre ramas publicadas salvo autorizacion explicita y documentada.
- El working tree debe quedar limpio al cierre de cada version.

## Multitenancy y ownership

- Toda escritura valida `organization_id`, `event_id` y ownership real de las entidades relacionadas.
- No se confia en IDs enviados por cliente cuando el contexto puede resolverse en backend.
- Las consultas administrativas filtran por organizacion y evento.
- Los endpoints publicos exponen solo datos publicados y minimizados.

## RBAC

- Toda operacion sensible tiene permiso backend explicito.
- La UI no reemplaza las validaciones del backend.
- Los permisos se documentan por version y se agregan de forma compatible.

## Auditoria

- Crear, publicar, asignar, cerrar, archivar, validar, exportar y usar tokens debe quedar auditado.
- La auditoria no debe guardar secretos, tokens completos ni datos privados innecesarios.

## Idempotencia

- Las operaciones repetibles usan claves idempotentes o restricciones equivalentes.
- Los reintentos no deben duplicar efectos externos ni registros criticos.

## Feature flags

- Toda nueva funcion queda detras de feature flag.
- Flag OFF conserva el comportamiento anterior.
- Los flags pueden aplicarse a plataforma, organizacion o evento segun el dominio.

## Migraciones

- Las migraciones son aditivas salvo decision documentada.
- No se alteran migraciones historicas ya aplicadas.
- SQLite y PostgreSQL deben seguir siendo compatibles cuando el modulo lo requiera.

## Backup y restore

- Nuevas tablas y storage se integran al backup/restore correspondiente.
- Restore como evento nuevo debe remapear IDs y conservar aislamiento.
- Tokens restaurados quedan inactivos cuando su reutilizacion pueda producir efectos inseguros.

## Upgrade

- Cambios de esquema se documentan con impacto en upgrade.
- Cambios medios o altos activan evaluacion de recertificacion.

## Seguridad y secretos

- No se versionan `.env`, tokens, dumps, storage crudo ni credenciales.
- No se imprimen secretos en logs, auditoria, errores ni reportes.
- Cargas de archivos validan extension, MIME, tamano, ownership y rutas seguras.

## Regresion

- Cada version ejecuta su verificador propio y regresion de versiones previas afectadas.
- Gates fallidos bloquean merge.
- No se marca PASSED sin evidencia reproducible.

## Documentacion y reportes

- Cada version incluye baseline, alcance, modelo, API, RBAC, seguridad, multitenancy, backup/restore, regresion y reporte final.
- Los reportes documentan hallazgos, correcciones, pruebas y riesgos residuales.

## Observabilidad

- Health checks y smoke tests deben conservarse sanos.
- Nuevos procesos o jobs deben emitir estados diagnosticos sin datos sensibles.

## Criterios de bloqueo

Detener ante secretos, cross-tenant, cross-event, perdida de datos, migracion inconsistente, restore fallido, hallazgo HIGH, PR bloqueado o working tree no controlado.

## Release Candidate

- No se modifica una RC congelada.
- No se declara release estable sin certificacion formal.
- No se ejecuta Endurance 24h sin orden expresa.
