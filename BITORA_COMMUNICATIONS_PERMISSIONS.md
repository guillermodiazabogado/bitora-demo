# BITORA - Integracion de Comunicaciones con Usuarios y Permisos

## Estado

El Centro de Comunicaciones queda integrado con el sistema actual de usuarios, eventos, roles por evento y matriz editable.

No se creo un segundo sistema de usuarios ni una matriz paralela.

## Archivos modificados

- `server.py`
- `frontend/app.js`
- `frontend/styles.css`
- `static/app.js`
- `static/styles.css`
- `verificar_comunicaciones_permisos.py`

## Permisos finos agregados

- `communications.view`
- `communications.create`
- `communications.edit`
- `communications.preview`
- `communications.select_audience`
- `communications.send`
- `communications.schedule`
- `communications.pause`
- `communications.resume`
- `communications.cancel`
- `communications.resend_individual`
- `communications.view_history`
- `communications.view_metrics`
- `communications.manage_templates`
- `communications.approve_templates`
- `communications.manage_providers`
- `communications.view_technical_logs`
- `communications.retry_failed`
- `communications.export`
- `communications.view_personal_data`
- `communications.manage_consent`

## Backend

Se agrego autorizacion centralizada por:

- usuario autenticado;
- evento activo;
- asignacion del usuario al evento;
- rol efectivo dentro del evento;
- permiso fino requerido.

La funcion central es:

`require_event_permission(db, event_id, permission_code, action)`

Tambien se agrego:

`user_has_permission(db, session, event_id, permission_code)`

## Endpoints protegidos en esta etapa

- `GET /api/communications`
- `GET /api/communications/history`
- `GET /api/communications/assistant/history`
- `POST /api/communications/send`
- `POST /api/communications/email/send`
- `POST /api/communications/whatsapp/send`
- `POST /api/communications/email/test`
- `POST /api/communications/whatsapp/test`
- `POST /api/communications/email/retry`
- `POST /api/communications/assistant/message`

## Separacion create/send

Crear no implica enviar.

Si `confirm=false`, la operacion requiere:

`communications.create`

Si `confirm=true`, la operacion requiere:

`communications.send`

El reenvio individual por acreditacion requiere:

`communications.resend_individual`

## Enmascaramiento

Si el usuario no tiene:

`communications.view_personal_data`

el backend enmascara email, telefono y destinatario en respuestas de comunicaciones.

## Auditoria

Se auditan:

- permisos denegados;
- comunicaciones encoladas;
- pruebas tecnicas;
- reintentos;
- cambios de matriz de permisos.

## Frontend

El Centro de Comunicaciones ahora adapta:

- formulario de nueva comunicacion;
- seleccion de audiencia;
- confirmacion de envio;
- metricas;
- historial;
- plantillas;
- pruebas de proveedores.

La matriz de permisos muestra:

- pestanas visibles;
- permisos finos de Comunicaciones.

## Pruebas

Se agrego:

`verificar_comunicaciones_permisos.py`

Valida:

- Productor puede enviar en evento asignado;
- Productor no puede enviar en evento no asignado;
- Comunicaciones de borrador no procesan envio;
- Recepcion puede tener reenvio individual sin envio masivo;
- Soporte tecnico ve logs tecnicos pero no datos personales;
- enmascaramiento de datos personales.

## Riesgos pendientes

- Crear entidades formales de comunicacion tipo borrador/campana, separadas de la cola.
- Implementar endpoints especificos de pausa, reanudacion, cancelacion y programacion.
- Agregar gestion editable de plantillas desde UI con `manage_templates` y `approve_templates`.
- Integrar logs tecnicos detallados de proveedores reales cuando WhatsApp/email esten activos.
- Completar pruebas HTTP end-to-end con sesiones reales y roles por evento.
