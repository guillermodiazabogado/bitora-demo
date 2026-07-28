# BITORA V4 Zone Permissions Architecture

## Zonas

Acceso general, escenario, backstage, prensa, camarines, tecnica, VIP, exposicion, sala especifica y actividad especifica.

## Modelo Conceptual

Una zona pertenece a evento. Puede tener jerarquia, vigencia y reglas horarias. Una persona obtiene permiso por acreditacion, rol, invitacion o excepcion auditada.

## Decisiones

Denegacion explicita prevalece sobre permiso heredado. Permisos temporales vencen. Cambios durante evento se auditan y aplican al siguiente escaneo.

## Control Offline

Offline solo puede operar con snapshot firmado, expiracion corta y sincronizacion posterior con deteccion de conflicto.

## Criterios

- Acceso ajeno: denegado.
- Zona vencida: denegada.
- Denegacion explicita: denegada.
- Excepcion sin motivo: bloqueada.
