# BITORA Google OAuth Setup Guide

## Variables

Configurar solamente en `deployment/staging/.env.staging` o en el entorno cloud. No versionar secretos.

```text
GOOGLE_OAUTH_ENABLED=true
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8788/api/integrations/google/callback
GOOGLE_OAUTH_SCOPES=openid email profile
GOOGLE_OAUTH_STATE_TTL_MINUTES=10
```

## Google Cloud

Crear una app OAuth de prueba.

Configurar Redirect URI exacta:

```text
http://localhost:8788/api/integrations/google/callback
```

Para staging publico usar la URL publica equivalente:

```text
https://<staging-domain>/api/integrations/google/callback
```

## Flujo operativo

1. Entrar a BITORA como usuario autorizado.
2. Abrir Configurar Evento.
3. Crear integracion Google.
4. Presionar Conectar Google.
5. Completar consentimiento en Google.
6. Volver por callback.
7. Probar conexion.

## Scopes iniciales

```text
openid
email
profile
```

No agregar scopes amplios hasta que una funcionalidad real los requiera.
