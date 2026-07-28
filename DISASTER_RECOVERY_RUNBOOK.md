# DISASTER_RECOVERY_RUNBOOK

## Proposito

Reconstruir staging desde un backup multitenant certificado, sin efectos externos y con medicion de RPO/RTO.

## Comando

```bash
python deployment/scripts/certify_disaster_recovery_live.py
```

## Flujo

1. Validar existencia del backup certificado.
2. Copiar dump y storage fuera de los volumenes Docker.
3. Destruir contenedores y volumenes de staging.
4. Levantar PostgreSQL vacio.
5. Restaurar base desde `database.dump`.
6. Restaurar storage desde `storage.tar.gz`.
7. Levantar app y monitor.
8. Validar manifiestos, seguridad e aislamiento.
9. Levantar worker y confirmar cero efectos externos.
10. Registrar RPO/RTO y evidencia BSTF.

## Seguridad

- Solo usar `APP_ENV=staging`.
- No versionar artefactos de backup.
- No iniciar tuneles publicos.
- No imprimir secretos.
- Mantener safe mode.
