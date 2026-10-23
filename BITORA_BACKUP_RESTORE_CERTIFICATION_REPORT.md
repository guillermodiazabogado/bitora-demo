# BITORA Backup/Restore Certification Report

Fecha: 2026-08-11  
Staging: https://bitora-staging.onrender.com  
Commit online auditado: 24f891ff767c1d92bcdd7edb81c71e87caf8ab67  
Rama de trabajo: feature/staging-persistence-stability-certification

## Resultado

| Control | Estado |
| --- | --- |
| PostgreSQL live | PASSED |
| Storage local operativo | PASSED |
| Storage persistente Render | BLOCKED |
| Backup disponible en `/health` | FAILED |
| Backup real de staging | BLOCKED |
| Checksum de backup | N/A |
| Restore aislado | BLOCKED |
| Integridad post-restore | N/A |
| Restart persistence | BLOCKED |

## Evidencia

`/health` respondio correctamente, con PostgreSQL online, jobs en cero y storage local listo, pero reporto:

```text
backup = missing
storage.backend = local
storage.ready = true
```

`/ready` respondio `ready`, pero mantuvo la advertencia:

```text
Storage local requiere disco persistente y backup externo
```

`render.yaml` configura:

```text
BITORA_STORAGE_PATH=/bitora/storage
BITORA_BACKUP_PATH=/bitora/backups
```

No hay Persistent Disk declarado para el servicio web de Render.

## Causa del bloqueo

El almacenamiento local del servicio web en Render no puede certificarse como persistente sin un Persistent Disk o un backend externo autorizado. El servicio actual esta definido en plan `free`, y Render documenta que los servicios web gratis no preservan cambios del filesystem local mediante Persistent Disk.

## Decision tecnica

No se ejecuto backup/restore live porque el prerequisito de persistencia real no esta cumplido. Ejecutarlo ahora produciria evidencia no certificable.

## Accion requerida

1. Autorizar hosting persistente.
2. Habilitar Render Persistent Disk o definir backend externo autorizado.
3. Montar storage y backups en rutas persistentes.
4. Reiniciar staging.
5. Verificar `/health` sin `backup=missing`.
6. Ejecutar backup real.
7. Restaurar en entorno aislado.
8. Comparar manifiestos y checksums.

## Estado final

backup_multitenant_live: BLOCKED  
restore_multitenant_live: BLOCKED  
Motivo: requiere aprobacion de hosting persistente.
