# BITORA V4 Autocomplete Architecture

## Objetivo

Reutilizar datos autorizados para acelerar registro y recepcion sin revelar informacion ajena ni asumir identidad.

## Fuentes

Usuario autenticado, historial de la organizacion, inscripcion anterior, invitacion y contacto autorizado.

## Prioridad

Datos confirmados por el usuario activo prevalecen. Datos de organizacion son sugerencias. Datos divergentes se muestran como conflicto, no se sobrescriben solos.

## Campos Protegidos

Email, documento, telefono, consentimiento, datos sensibles y campos verificados requieren confirmacion.

## Deduplicacion

Email normalizado es clave inicial, complementada por documento o telefono si existe. Coincidencias ambiguas no autocompletan.

## Auditoria

Debe registrarse fuente, campo sugerido, campo aceptado, actor y motivo cuando aplique.
