# BITORA V5 Discovery - Security Review

## Estado Actual Observado

Existe:

- login por usuario/PIN/password hash;
- roles y permisos por evento;
- user_event_roles;
- organizations y organization_users;
- IntegrationSecretService para secretos;
- Safe Mode para email/WhatsApp;
- tokens QR unicos;
- audit_logs;
- backup/restore con token regeneration;
- health/ready.

## Recomendaciones

### CRITICAL

Ninguna vulnerabilidad critica demostrada en discovery documental.

### HIGH

- Formalizar Device API con autenticacion de terminal antes de offline/edge.
- Endurecer Resend/email: dominio verificado, webhook secret, remitente propio y pruebas de entrega antes de operar comunicaciones reales.
- Separar Permission administrativa de Entitlement operativo para evitar escaladas conceptuales.
- Agregar revocacion central de credenciales/tokens antes de QR dinamico/NFC.

### MEDIUM

- Convertir auditoria critica a append-only o hash chained para operaciones sensibles.
- Rate limiting explicito para login, portal token y validate.
- Contratos de CORS/CSRF documentados y verificados.
- Secret scan como gate obligatorio de PR.
- Validar que backups no contengan secretos operativos o datos fuera de alcance.

### LOW

- Mejorar mascarado de errores de proveedor en UI.
- Documentar politica de retencion de logs.
- Unificar nombres de roles/permisos en matriz unica.

## Riesgos V5

- Offline puede permitir acceso con dataset vencido.
- Hardware externo puede introducir bypass si no pasa por Device API.
- Entitlements mal modelados pueden duplicar permisos y acceso.
- Lead retrieval requiere consentimiento y scope por empresa/stand.

## Controles Requeridos Para V5

- idempotency keys obligatorias;
- correlation_id en operaciones criticas;
- device_id en access events;
- event_id + organization_id en todas las escrituras;
- logs sin secretos;
- Safe Mode por defecto para comunicaciones.
