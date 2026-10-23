# BITORA_V4_OPERATIONS_GUIDE

## Operacion segura V4

1. Verificar `APP_ENV`.
2. Confirmar Safe Mode antes de pruebas.
3. Ejecutar `python deployment/scripts/bdf.py health`.
4. Ejecutar `python deployment/scripts/bdf.py migrate`.
5. Ejecutar `python deployment/scripts/bdf.py smoke-test`.
6. Antes de pruebas destructivas, generar backup.
7. Mantener credenciales fuera de Git.
8. No activar Live Mode sin ventana de prueba autorizada.

## Cierre funcional

Usar los verificadores V4.1 a V4.10 como control de regresion antes de cualquier PR que toque dominio, permisos, storage, jobs, comunicaciones o analytics.
