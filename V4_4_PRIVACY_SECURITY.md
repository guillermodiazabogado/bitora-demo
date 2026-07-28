# BITORA V4.4 - Privacy and Security

## Tokens

Los tokens de acceso se generan con entropia alta, se guardan como SHA-256 y solo se expone un `token_hint`. No se registran tokens completos en auditoria ni reportes.

## Anonimato

En encuestas anonimas, las respuestas no almacenan `participant_id`. La deduplicacion se apoya en una tabla separada de tokens y en un `anonymous_subject_hash` calculado con secreto interno.

Limite documentado: el anonimato no es anonimato estadistico absoluto. Un administrador tecnico con acceso total a base y secretos podria correlacionar metadatos operativos. La UI y los reportes administrativos no reconstruyen identidad.

## Aislamiento

Todas las operaciones administrativas filtran por `organization_id` y `event_id`. Las respuestas validan asignacion, encuesta, version, participante/token y estado de apertura.

## Exportacion

La exportacion CSV neutraliza valores potencialmente ejecutables para reducir CSV injection.

## Auditoria

Se auditan operaciones administrativas: creacion, versionado, publicacion, asignacion, cierre, archivo y exportacion. No se copian respuestas sensibles completas al log administrativo.
