# Webhooks Multi-Tenant

## Flujo requerido

Webhook recibido -> firma -> proveedor -> mensaje -> integracion -> organizacion -> evento -> actualizacion idempotente.

## Protecciones

- Firma invalida rechazada.
- Duplicados idempotentes.
- Eventos tardios aceptados solo si pertenecen al mensaje correcto.
- No exponer secretos en logs.

## Prueba

```bash
python verificar_webhooks_multitenant_live.py
```

La prueba actual valida contrato e idempotencia local. La resolucion live requiere payload real del proveedor.
