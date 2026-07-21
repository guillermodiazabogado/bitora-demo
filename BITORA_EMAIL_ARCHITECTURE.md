# BITORA - Arquitectura de Email Productivo

## Estado

BITORA incorpora una capa desacoplada de email productivo.

Proveedor inicial:

- Resend.

Arquitectura preparada para:

- SendGrid;
- Mailgun;
- Amazon SES;
- SMTP transaccional futuro.

## Flujo

```text
Centro de Comunicaciones
  -> backend valida permisos/evento/audiencia
  -> communication_queue
  -> worker/procesador de email
  -> EmailProvider
  -> proveedor externo
  -> webhook
  -> email_delivery_events
  -> communication_queue
  -> communication_logs
  -> auditoria
```

El frontend nunca envia directo al proveedor.

## Proveedor

Interfaz:

- `EmailProvider`
- `send_email`
- `send_template`
- `get_delivery_status`
- `validate_configuration`
- `normalize_webhook`

Implementaciones:

- `DemoEmailProvider`
- `ResendEmailProvider`

## Variables

```env
EMAIL_PROVIDER=resend
EMAIL_ENABLED=true
EMAIL_API_KEY=
EMAIL_FROM=BITORA <eventos@tu-dominio.com>
EMAIL_FROM_NAME=BITORA
EMAIL_FROM_ADDRESS=eventos@tu-dominio.com
EMAIL_REPLY_TO=
EMAIL_VERIFIED_DOMAIN=tu-dominio.com
EMAIL_WEBHOOK_SECRET=
EMAIL_SAFE_MODE=false
EMAIL_FORCE_RECIPIENT=
EMAIL_TEST_RECIPIENT=
EMAIL_MAX_BATCH_SIZE=50
EMAIL_RATE_LIMIT=60
EMAIL_MAX_RETRIES=3
EMAIL_RETRY_BASE_SECONDS=60
EMAIL_TIMEOUT_SECONDS=15
```

## Seguridad

No se expone:

- API key;
- webhook secret;
- tokens;
- cuerpos completos en diagnostico.

En produccion BITORA exige:

- `EMAIL_API_KEY`;
- remitente configurado;
- dominio verificado;
- webhook secret;
- safe mode desactivado.

## Supresion

Tabla:

```text
email_suppressions
```

Motivos:

- `hard_bounce`;
- `complaint`;
- `invalid_email`;
- `manual`;
- `unsubscribe`.

El sistema no elimina personas. Solo bloquea nuevos envios segun alcance.

## Idempotencia

Cada email en cola puede tener:

```text
idempotency_key
```

Esto evita duplicados por:

- doble click;
- reintento;
- worker repetido;
- reinicio;
- solicitud duplicada.

## Webhooks

Los webhooks:

- validan firma Svix/Resend cuando hay secreto;
- rechazan eventos incompletos;
- registran `external_event_id`;
- evitan duplicados;
- normalizan estados;
- actualizan cola;
- registran historial;
- auditan.

Estados normalizados:

- `enviado`;
- `entregado`;
- `rebotado`;
- `rechazado`;
- `abierto`;
- `click`;
- `error`;
- `pendiente`.

## Diagnostico

El Centro de Comunicaciones expone, sin secretos:

- proveedor;
- enabled;
- ready;
- safe mode;
- remitente;
- dominio verificado;
- ultimo envio exitoso;
- ultimo error;
- errores de configuracion para usuarios tecnicos.

## Pendientes Reales

Para declarar email productivo completo falta ejecutar prueba real:

1. verificar dominio en Resend;
2. cargar DNS;
3. configurar `EMAIL_API_KEY`;
4. configurar webhook;
5. enviar email de prueba;
6. confirmar entrega;
7. recibir webhook delivered;
8. validar historial y metricas.
