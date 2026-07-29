# BITORA_V4_ROLLBACK_GUIDE

## Politica

Si un despliegue V4 falla, la estrategia preferida es restaurar desde backup certificado antes de reactivar workers o integraciones externas.

## Pasos generales

1. Activar modo seguro.
2. Pausar workers.
3. Bloquear comunicaciones reales.
4. Verificar backup disponible.
5. Restaurar base y storage en entorno controlado.
6. Ejecutar health checks.
7. Ejecutar smoke-test.
8. Ejecutar verificadores afectados.
9. Reactivar servicios gradualmente.

## Restricciones

- No ejecutar jobs externos automaticamente tras restore.
- No renovar tokens externos automaticamente en entorno restaurado.
- No abrir tuneles publicos durante rollback salvo necesidad documentada.
