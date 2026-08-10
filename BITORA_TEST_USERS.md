# BITORA Test Users

Este documento lista usuarios base de prueba para entornos local/staging.

No contiene contraseñas.

Las contraseñas temporales deben generarse localmente con:

```bash
python scripts/bootstrap_test_users.py --reset
```

## Usuarios Base

| Usuario | Rol | Uso |
| --- | --- | --- |
| superadmin-demo | Super Admin | Administracion global y configuracion completa |
| admin-demo | Super Admin | Administracion alternativa de pruebas |
| coordinador-demo | Coordinador | Operacion coordinada del evento |
| productor-demo | Productor | Home Visual de Productor y gestion operativa |
| recepcion-demo | Operador de recepcion | Recepcion y acreditacion |
| acceso-demo | Operador de acceso | Validacion QR y zonas |
| visualizador-demo | Visualizador | Lectura y reportes sin escritura |
| comunicaciones-demo | Comunicaciones | Centro de comunicaciones |
| soporte-demo | Soporte tecnico | Diagnostico tecnico y auditoria |

## Reglas

- No usar estos usuarios en produccion.
- No guardar contraseñas en Git.
- No compartir contraseñas en reportes.
- Rotar cualquier contraseña que haya sido expuesta accidentalmente.
- Mantener `must_change_password` activo tras bootstrap.
