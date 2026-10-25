# BITORA V5 Discovery - Compatibility and Migration

## Contratos Que No Deben Romperse

- URLs publicas actuales: /, /login.html, /p.html, /print.html.
- /api/portal?token=TOKEN.
- /api/qr.svg?token=TOKEN.
- /api/validate.
- /api/accreditations.
- /api/register.
- exports CSV/JSON.
- backups ZIP.
- event_id, person_id, accreditation_id.
- accreditations.token existentes.

## Estrategia De Migracion

1. Agregar tablas aditivas V5.
2. Poblar shadow model desde V4 sin usarlo para decidir.
3. Ejecutar comparador: decision V4 vs decision V5.
4. Activar feature flag por evento piloto.
5. Mantener rollback a motor V4.
6. Incluir tablas V5 en backup/restore antes de usar en piloto real.

## Rollback

Todo ExecPlan V5 debe poder desactivarse por feature flag.

Rollback minimo:

- apagar feature flag;
- conservar datos V5 como evidencia;
- volver a decision V4;
- no borrar datos hasta auditoria.

## Backups

Cualquier tabla V5 que impacte acceso, entitlement o device debe entrar en backup/restore en el mismo ExecPlan.

## Breaking Change Proposals

Ninguna aprobada.

Potenciales breaking changes futuros que requieren decision humana:

- cambiar semantica de QR token;
- eliminar uniqueness global de people.email;
- reemplazar /api/validate por endpoint nuevo obligatorio;
- exigir device auth para todos los accesos;
- cambiar formato de backup.
