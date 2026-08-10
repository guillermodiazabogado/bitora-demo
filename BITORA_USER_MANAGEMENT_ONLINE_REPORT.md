# BITORA User Management Online Report

## Estado

Estado inicial: DEPLOYMENT PREPARED

## Fuente

- Initial develop/v4 solicitado: `aec70159755b2d674c4f96267c06bba8ab585ff3`
- Source SHA usado: `147ea4bfe64be394fed2d33f67c19b0249fb7849`
- Motivo del descendiente: correccion de compatibilidad local de migracion email detectada al preparar usuarios.
- Deployment branch: `deployment/v4-online`
- Render URL: `https://bitora-staging.onrender.com`

## Predeploy

- Syntax backend: PASSED
- Syntax frontend: PASSED
- `verificar_user_management_v4.py`: PASSED
- `verificar_home_productor.py`: PASSED
- Secretos nuevos versionados: 0

## Health Render Previo

- `/health`: PASSED
- `/ready`: PASSED
- Environment: staging
- PostgreSQL: PASSED
- Safe Mode: ON
- Live Mode: OFF
- Persistent Disk: NOT CHANGED

## Pendiente Postdeploy

- Deploy de `deployment/v4-online`.
- Migracion 026 en Render.
- Validacion online Admin.
- Validacion online Productor.
- Reset password online.
- Desactivar/reactivar online.
- RBAC online.

## Recuperacion Admin Staging

Se agrego un mecanismo controlado para recuperar el usuario admin de staging cuando la clave operativa se perdio.

Condiciones:

- solo opera con `APP_ENV=staging`;
- requiere `BITORA_ADMIN_BOOTSTRAP_USER`;
- requiere `BITORA_ADMIN_BOOTSTRAP_PASSWORD` fuerte;
- requiere `BITORA_ADMIN_BOOTSTRAP_RESET_TOKEN`;
- registra auditoria `user.bootstrap_admin_reset`;
- el mismo token de reset no se reutiliza;
- no imprime ni versiona passwords, hashes ni tokens.

No aplica en produccion.

## Restricciones Mantenidas

- Production: NOT TOUCHED
- Endurance: DEFERRED
- PR #12: UNCHANGED
- Persistent Disk: NOT CHANGED
- WhatsApp/Meta: NOT TOUCHED
