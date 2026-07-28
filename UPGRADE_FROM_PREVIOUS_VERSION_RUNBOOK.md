# UPGRADE_FROM_PREVIOUS_VERSION_RUNBOOK

## Versiones

- Origen: `c3ae63585c53105c2e99912148df0be8ae803afb`
- Destino: `524f13890c1df02e095077f9fc58204042b1682d`

## Comando

```bash
python deployment/scripts/certify_upgrade_from_previous_live.py
```

## Flujo

1. Exportar la version anterior real con `git archive`.
2. Crear entorno Docker aislado `BITORA-UPGRADE-SOURCE`.
3. Levantar PostgreSQL, app, storage y worker controlado.
4. Generar dataset con la version anterior.
5. Crear manifiesto y backup pre-upgrade.
6. Detener app/worker para quiescence.
7. Cambiar la imagen de app al commit objetivo.
8. Ejecutar migraciones reales e idempotencia.
9. Comparar manifiestos pre/post.
10. Validar seguridad, aislamiento, storage y jobs.
11. Simular restore fallido y recuperar desde backup pre-upgrade.
12. Apagar y eliminar entorno temporal.

## Politica De Recuperacion

Las migraciones no se declaran reversibles. La politica oficial ante fallo es restore del backup pre-upgrade.
