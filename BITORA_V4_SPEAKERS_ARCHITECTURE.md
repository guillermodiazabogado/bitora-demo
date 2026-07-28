# BITORA V4 Speakers Architecture

## Perfiles

Usuario interno, disertante invitado, disertante sin cuenta, representante y asistente.

## Flujo

`draft` -> `invited` -> `accepted` -> `pending_information` -> `validated` -> `published` -> `cancelled`.

## Datos

Perfil, biografia, fotografia, documentacion, actividades, disponibilidad, requisitos tecnicos, materiales, presentacion y contactos.

## Ownership

La entidad speaker pertenece a organizacion. Sus asignaciones pertenecen a evento y actividad. Materiales se guardan bajo storage aislado por evento u organizacion segun uso.

## Permisos

El disertante edita solo su perfil y materiales asignados. Productor valida y publica. Auditor ve cambios sanitizados.

## Criterios

- Invitacion no crea acceso global innecesario.
- Materiales no exponen otros eventos.
- Publicacion requiere validacion.
