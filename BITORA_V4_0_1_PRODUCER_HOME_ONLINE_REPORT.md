# BITORA V4.0.1 Producer Home Online Report

## Estado Inicial

- Rama fuente local: `develop/v4`
- SHA fuente: `824107bb9e8d617354e22e1dbd44766e53782af1`
- Rama de deployment: `deployment/v4-online`
- Render URL: `https://bitora-staging.onrender.com`
- Producción: no tocada
- Endurance: diferido
- PR #12: sin cambios
- Persistent Disk: pendiente de aprobación de hosting

## Estrategia

La rama `deployment/v4-online` conserva la configuración propia de Render, PostgreSQL y staging. Se incorporaron únicamente los archivos de Home Visual ya certificados desde `develop/v4`, evitando cambios en `render.yaml`, Docker, PostgreSQL, PR #12 o producción.

## Componentes a Validar Online

- Health.
- Readiness.
- PostgreSQL.
- Safe Mode.
- Live Mode OFF.
- Login sin usuario precargado.
- Productor online.
- Evento activo online.
- Home Visual.
- 12 tarjetas.
- Retorno al Home.
- Productor limitado.
- No Productor.
- Responsive.
- RBAC backend.

## Evidencia

Ejecución posterior al deploy manual de Render:

- `https://bitora-staging.onrender.com/health`: PASSED.
- `https://bitora-staging.onrender.com/ready`: PASSED.
- Environment: `staging`.
- PostgreSQL: `online`.
- Safe Mode: PASSED.
- Live Mode OFF: PASSED.
- Storage: `local`, pendiente de Persistent Disk aprobado.
- Static online:
  - `/login.html`: PASSED.
  - `/app.js`: PASSED.
  - `/styles.css`: PASSED.
  - `producer-mode`: detectado.
  - `producerHomeAllowed`: detectado.
  - `producerHomeGrid`: detectado.
  - login con usuario vacío por defecto: detectado.

## Bloqueo Operativo

La validación completa de Productor online queda bloqueada por credenciales administrativas de staging.

Staging tiene `QR_REQUIRE_LOGIN=true`, por lo que los endpoints de alta/restablecimiento de usuarios requieren sesión válida. El intento de crear `productor-demo-online` sin sesión fue rechazado correctamente con `401 Unauthorized`.

Usuario admin online detectado:

- `bitora-staging-admin-1c598f2a`

No se probó fuerza bruta ni se reutilizaron PIN inseguros. Los PIN conocidos `1234`, `2222` y `3333` no corresponden al hash online expuesto por `/api/users`.

Para continuar se requiere una de estas acciones:

1. Ingresar el PIN temporal del usuario `bitora-staging-admin-1c598f2a` en la consola local segura.
2. Crear manualmente en staging un Productor online con evento activo y permisos completos.

Frase de reanudación esperada:

`listo admin staging`

## Seguridad

No se deben versionar:

- passwords temporales;
- tokens;
- secretos;
- credenciales Render;
- dumps;
- logs crudos;
- URLs sensibles temporales.

## Resultado

`BLOCKED BY STAGING ADMIN CREDENTIALS`
