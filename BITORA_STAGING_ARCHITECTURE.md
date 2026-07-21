# BITORA Staging Architecture

## Objetivo

El entorno staging de BITORA existe para ejecutar pruebas de release, disaster recovery, endurance y PostgreSQL live sin tocar la demo publica ni datos reales.

## Componentes

- `bitora-staging-app`: aplicacion BITORA.
- `bitora-staging-postgres`: PostgreSQL real y aislado.
- `bitora-staging-storage`: volumen persistente para archivos por evento.
- `bitora-staging-backups`: volumen persistente para backups.
- `bitora-staging-logs`: volumen persistente para logs.
- Worker interno: levantado por la aplicacion y monitoreado por diagnostico tecnico.

## Aislamiento

Staging debe usar:

- `APP_ENV=staging`.
- base PostgreSQL separada;
- storage separado;
- backups separados;
- credenciales de prueba;
- safe mode obligatorio para email y WhatsApp;
- destinatarios forzados.

## Red

La aplicacion se expone localmente en `http://localhost:8788` cuando se usa Docker Compose.
PostgreSQL se expone en `localhost:55432` solo para administracion local.

## Regla operativa

Las pruebas destructivas, de disaster recovery y endurance solo se ejecutan en staging. Nunca deben ejecutarse en la demo publica ni en produccion.
