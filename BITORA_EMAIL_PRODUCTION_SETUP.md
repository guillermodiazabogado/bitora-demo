# BITORA - Setup Email Productivo

## 1. Dominio

Usar dominio o subdominio propio.

Ejemplo:

```text
eventos.midominio.com
```

No usar Gmail, Hotmail ni cuentas personales para envio masivo.

## 2. DNS

Configurar en el proveedor:

- SPF;
- DKIM;
- DMARC;
- return-path si corresponde;
- tracking domain si se habilita tracking.

Para DMARC inicial:

```text
v=DMARC1; p=none; rua=mailto:dmarc@midominio.com
```

Luego endurecer gradualmente a `quarantine` o `reject`.

## 3. Resend

1. Crear cuenta.
2. Agregar dominio.
3. Copiar registros DNS.
4. Esperar verificacion.
5. Crear API key.
6. Configurar webhook.

Webhook:

```text
https://TU_DOMINIO/api/communications/email/webhook
```

Eventos sugeridos:

- sent;
- delivered;
- bounced;
- complained;
- failed;
- opened;
- clicked.

## 4. Variables Render/Railway

```env
EMAIL_PROVIDER=resend
EMAIL_ENABLED=true
EMAIL_API_KEY=...
EMAIL_FROM=BITORA <eventos@eventos.midominio.com>
EMAIL_FROM_ADDRESS=eventos@eventos.midominio.com
EMAIL_FROM_NAME=BITORA
EMAIL_REPLY_TO=contacto@midominio.com
EMAIL_VERIFIED_DOMAIN=eventos.midominio.com
EMAIL_WEBHOOK_SECRET=whsec_...
EMAIL_SAFE_MODE=false
EMAIL_TIMEOUT_SECONDS=15
EMAIL_MAX_RETRIES=3
```

## 5. Prueba Segura

Antes de enviar a participantes:

```env
EMAIL_SAFE_MODE=true
EMAIL_FORCE_RECIPIENT=tu-email@dominio.com
```

Esto fuerza destinatario de prueba y marca asunto con `[SAFE]`.

Luego, para produccion real:

```env
EMAIL_SAFE_MODE=false
EMAIL_FORCE_RECIPIENT=
```

## 6. Validacion

Ejecutar:

```bash
python verificar_v6_1_email_productivo.py
```

Luego hacer prueba real desde:

```text
Centro de Comunicaciones -> Email de prueba
```

Confirmar:

- llega el correo;
- aparece `provider_message_id`;
- webhook marca delivered;
- historial queda registrado;
- auditoria queda registrada.

## 7. Recomendacion de Entregabilidad

Primeros envios:

- empezar con pocos destinatarios;
- evitar bases viejas;
- revisar rebotes;
- mantener asunto claro;
- incluir contacto;
- no usar palabras engañosas;
- calentar dominio progresivamente.
