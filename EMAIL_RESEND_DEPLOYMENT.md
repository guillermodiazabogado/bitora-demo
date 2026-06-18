# BITORA V6.1 - Email real con Resend

## Arquitectura

Los envios siguen este recorrido:

`Centro de Comunicaciones -> communication_queue -> EmailProvider -> Resend -> webhook -> historial -> auditoria`

La interfaz no llama a Resend directamente. `EmailProvider` permite incorporar despues SendGrid, Mailgun o SMTP sin cambiar la logica del Centro de Comunicaciones.

## Variables

```env
EMAIL_PROVIDER=resend
EMAIL_API_KEY=re_xxxxxxxxx
EMAIL_FROM=BITORA <eventos@tu-dominio.com>
EMAIL_REPLY_TO=soporte@tu-dominio.com
EMAIL_ENABLED=true
EMAIL_MAX_RETRIES=3
EMAIL_WEBHOOK_SECRET=whsec_xxxxxxxxx
```

`EMAIL_API_KEY` y `EMAIL_WEBHOOK_SECRET` deben cargarse como secretos del servicio y nunca subirse al repositorio.

## Configuracion en Resend

1. Verificar el dominio remitente.
2. Crear una API Key con permiso de envio.
3. Configurar el webhook hacia `https://tu-dominio/api/communications/email/webhook`.
4. Suscribir los eventos de envio, entrega, rebote, queja y error.
5. Copiar el secreto de firma en `EMAIL_WEBHOOK_SECRET`.

## Prueba

1. Ingresar a BITORA como `Super Admin`.
2. Abrir `Configurar Evento`.
3. Revisar `Comunicaciones por email`.
4. Indicar una direccion y pulsar `Enviar email de prueba`.
5. Confirmar el estado en Centro de Comunicaciones, historial y auditoria.

## Seguridad y operacion

- En produccion, un webhook sin firma valida se rechaza.
- No se envia a participantes sin consentimiento de email.
- Los errores respetan `EMAIL_MAX_RETRIES` y luego pasan a `error`.
- El reintento manual usa `POST /api/communications/email/retry`.
- Las claves nunca se devuelven por API ni se muestran en la interfaz.

## Validacion automatica

```powershell
python verificar_v5_communications.py
python verificar_v5_email.py
python verificar_v6_1_email_real.py
python verificar_integridad_bitora.py
python verificar_convivencia_modulos.py
```

La prueba V6.1 levanta un proveedor Resend falso local. No consume API real ni envia correos externos.
