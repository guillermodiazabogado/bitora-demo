# BITORA Security Baseline Report

Fecha: 2026-07-28

## Resultado

```text
Security Baseline: PASSED
seguridad_basica: PASSED
```

## Correccion Aplicada

Endpoint corregido:

```text
POST /api/accreditations/update
```

Cambios:

```text
Autorizacion por evento antes de modificar: PASSED
Permiso requerido manual_accredit: PASSED
Visualizador bloqueado con 403: PASSED
Payload parcial preserva datos existentes: PASSED
Auditoria con actor efectivo: PASSED
Errores de constraint antes de autorizacion: 0
```

## Pruebas Ejecutadas

```text
python verificar_seguridad_basica.py
python run_bitora_supertest.py --release
```

Resultado BSTF:

```text
seguridad_basica: PASSED
```

## Cobertura Del Gate

```text
Rol Acceso no puede configurar evento: PASSED
Rol Acceso no puede modificar cupos: PASSED
Rol Acceso no puede enviar comunicaciones masivas: PASSED
Rol Recepcion no puede preparar evento real: PASSED
Visualizador no puede editar datos: PASSED
Pantalla publica sin datos sensibles: PASSED
Sala de control sin DNI/email/telefono: PASSED
QR sin datos personales: PASSED
Portal participante aislado por token: PASSED
```

## Resultado De Seguridad

```text
Cruces detectados: 0
Secretos expuestos: 0
```
