# BITORA V4 Certificates Architecture

## Tipos

Participacion, asistencia, disertante, organizador, staff, aprobacion y horas cursadas.

## Contrato de Elegibilidad

Una elegibilidad combina asistencia minima, encuesta completada, actividad obligatoria, aprobacion manual y condiciones futuras como pago confirmado. La regla debe ser versionada y auditable.

## Ciclo de Vida

`draft`, `eligible`, `approved`, `issued`, `revoked`, `reissued`, `expired`.

## Componentes

Plantilla, variables, numeracion, codigo verificable, QR de validacion, firma, archivo emitido y registro de auditoria.

## Seguridad

El certificado pertenece a organizacion, evento y participante. La descarga publica debe usar token verificable no reutilizable para modificar datos. Revocacion no elimina evidencia historica.

## Emision

No se implementa PDF en este sprint. V4 debe disenar la emision como job idempotente y Safe Mode cuando implique envio.

## Criterios

- Certificado sin elegibilidad: bloqueado.
- Reemision conserva historial.
- Revocacion invalida verificacion publica.
- Backup/restore preserva estado y archivo.
