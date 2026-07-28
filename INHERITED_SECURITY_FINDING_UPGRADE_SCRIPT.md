# Inherited Security Finding - Upgrade Script

## Archivo

`deployment/scripts/certify_upgrade_from_previous_live.py`

## Regla

Auditoria estatica detecta una cadena con apariencia de password hardcodeado.

## Severidad

INHERITED_HIGH_FINDING

## Evidencia

Detectado antes de V4.1 durante BSTF quick sobre `develop/v4`.

## Relacion con V4.1

No forma parte del runtime de asistencia ni fue introducido por este sprint.

## Impacto Potencial

Puede afectar tooling de certificacion de upgrade si la cadena representa una credencial real o reutilizable. No se concluye que afecte runtime sin una revision dedicada.

## Motivo Para No Corregir Ahora

El sprint V4.1 tiene alcance cerrado sobre asistencia. Corregir tooling de upgrade podria requerir recertificacion de upgrade y debe separarse.

## Recomendacion

Crear sprint: `BITORA - INHERITED UPGRADE CERTIFICATION SECURITY REMEDIATION`.

## Gate Potencialmente Afectado

`upgrade_from_previous_version`

## Criterio de Resolucion

Eliminar o parametrizar la cadena, agregar regresion del upgrade script y repetir el gate afectado si corresponde.
