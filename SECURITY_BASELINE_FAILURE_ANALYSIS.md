# BITORA Security Baseline Failure Analysis

Fecha: 2026-07-28

Commit base:

```text
60dde6c78bed666e2ef33cbc1d9be774528dc30f
```

## Gate Investigado

```text
seguridad_basica: FAILED
```

## Prueba Ejecutada

```text
python verificar_seguridad_basica.py
```

## Criterio Esperado

Un usuario `Visualizador` no debe poder editar una acreditacion.

Resultado esperado:

```text
HTTP 403
```

## Falla Reproducida

Resultado real antes de la correccion:

```text
Visualizador edita: no fue bloqueado
status=409
duplicate key value violates unique constraint "people_email_key"
```

## Causa Raiz

El endpoint:

```text
POST /api/accreditations/update
```

validaba un rol operativo amplio mediante `can_actor`, pero no resolvia primero el evento de la acreditacion ni exigia permiso efectivo por evento antes de intentar actualizar datos.

Ademas, cuando el payload era parcial, campos no enviados quedaban como cadena vacia. En el caso de `email`, eso podia generar un error de unicidad antes de que la accion quedara bloqueada por permiso.

## Impacto

```text
Criticidad: alta
Riesgo: autorizacion tardia y error no sanitizado para actor sin permiso.
Datos modificados en la prueba: no, la transaccion fallo por constraint.
```

## Correccion Minima

Se cambio el flujo del endpoint para:

```text
1. Buscar la acreditacion y su event_id.
2. Validar require_event_permission(..., "manual_accredit", "accreditation.update", actor).
3. Bloquear antes de modificar datos si el actor no tiene permiso.
4. Preservar valores existentes cuando el payload es parcial.
5. Auditar con el usuario efectivo y event_id.
```

## Evidencia Posterior

```text
python verificar_seguridad_basica.py
OK: seguridad basica y permisos
```

BSTF Release:

```text
seguridad_basica: PASSED
```

## Secretos

```text
Secretos expuestos: 0
```
