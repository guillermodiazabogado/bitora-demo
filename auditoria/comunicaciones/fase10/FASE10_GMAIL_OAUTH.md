# Fase 10 - Gmail OAuth

## Resultado

- Gate de confianza OAuth: **PASS**.
- Autorizacion Gmail: **PASS**.
- Entrega real: **PASS**.

## Evidencia verificada

- Proyecto Google Cloud: `bitora-503116`, nombre BITORA.
- Cliente OAuth: `BITORA Staging Local`.
- Redirect URI: `http://localhost:8788/api/integrations/google/callback`.
- Scope solicitado: `https://www.googleapis.com/auth/gmail.send` solamente.
- Cuenta remitente configurada: `ag***@gmail.com`.
- El flujo llega a la pantalla oficial de Google sin `redirect_mismatch`.
- La aplicacion es externa y esta publicada, pero la marca/scope no estan verificados por Google.
- Causa de la advertencia: uso de un scope Gmail sensible sin aprobacion de verificacion.
- Causa del fallo anterior: `invalid_grant`, compatible con refresh token vencido o revocado.
- Contratos OAuth: state de un solo uso/expirable, acceso offline y no exposicion de secretos: PASS.
- Consentimiento completado por el propietario el 2026-11-13 sobre la cuenta remitente.
- Refresh token nuevo guardado directamente en Railway por stdin, sin exposicion.
- Redeploy de staging `bd33c9de-2396-4d4e-a96a-d5a20d00a02d`: SUCCESS; dos replicas saludables, `/ready` PASS y 55/55 migraciones.
- Prueba directa del proveedor Gmail: aceptada, con identificador de mensaje.
- Inscripcion publica sintetica: email encolado y procesado en un intento, estado `enviado`, sin error.
- Recepcion verificada en el buzon autorizado: asunto `[SAFE] Inscripcion confirmada`, contenido esperado del evento de staging.

## Persistencia prevista

El refresh token se intercambia localmente y se transmite por stdin al secreto Railway `GMAIL_REFRESH_TOKEN`. No se imprime, no se guarda en Git y no se incorpora a evidencias.

## Estado final del canal

Gmail queda habilitado y validado de extremo a extremo en staging. La autorizacion solo concede `gmail.send`; no se agregaron permisos de lectura ni se modifico produccion.
