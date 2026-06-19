# BITORA - Guía de experiencia en vivo para 10 personas

## Objetivo

Mostrar el recorrido completo:

1. El invitado abre la landing.
2. Completa sus datos.
3. Autoriza la confirmación por WhatsApp.
4. BITORA crea su acreditación y QR.
5. BITORA entrega el portal participante.
6. El worker procesa el WhatsApp.
7. El operador encuentra al invitado en recepción.
8. El QR se valida en acceso.
9. El segundo escaneo se rechaza como repetido.

## Preparación

En `Configurar Evento`, usar la tarjeta **Experiencia en vivo 10**.

El sistema crea:

- evento publicado;
- cupo total de 10;
- tipo Público General;
- Sala Demo;
- actividad reservable;
- pantalla pública;
- landing lista para compartir;
- base vacía, sin afectar otros eventos.

## WhatsApp

Variables necesarias:

```text
WHATSAPP_PROVIDER=meta
WHATSAPP_ENABLED=true
WHATSAPP_ACCESS_TOKEN=...
WHATSAPP_PHONE_NUMBER_ID=...
WHATSAPP_BUSINESS_ACCOUNT_ID=...
WHATSAPP_VERIFY_TOKEN=...
```

Para iniciar conversaciones sin que la persona escriba primero, Meta exige una plantilla aprobada:

```text
WHATSAPP_REGISTRATION_TEMPLATE=confirmacion_inscripcion
WHATSAPP_REGISTRATION_TEMPLATE_LANGUAGE=es_AR
WHATSAPP_REGISTRATION_TEMPLATE_VARIABLES=nombre,evento,portal
```

La plantilla debe tener tres variables, en ese orden:

1. nombre;
2. evento;
3. enlace al portal.

Si no hay plantilla aprobada, la confirmación de texto funciona dentro de la ventana de 24 horas iniciada por el participante.

## Guion sugerido

1. Mostrar la landing en pantalla.
2. Compartir el enlace o QR de captación.
3. Pedir a los invitados que completen el formulario y marquen WhatsApp.
4. Mostrar en el panel cómo aumenta el contador.
5. Abrir el portal recibido por uno de los invitados.
6. Mostrar el QR y la agenda.
7. Buscar al participante en Recepción.
8. Escanear el QR y mostrar “Acceso concedido”.
9. Escanearlo nuevamente y mostrar el rechazo por QR utilizado.
10. Abrir Comunicaciones y mostrar el historial del envío.

## Control previo

- Confirmar que Diagnóstico muestre WhatsApp conectado.
- Enviar un WhatsApp de prueba.
- Verificar el teléfono en formato internacional.
- Confirmar que el worker esté normal.
- Probar una inscripción propia antes de invitar a las diez personas.
- Mantener abierta una segunda pestaña con Recepción.
- Mantener un celular preparado como escáner.
