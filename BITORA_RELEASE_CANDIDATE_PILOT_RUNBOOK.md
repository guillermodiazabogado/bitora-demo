# BITORA_RELEASE_CANDIDATE_PILOT_RUNBOOK

## Preparacion

1. Confirmar tag `bitora-v1.0.0-rc.1`.
2. Confirmar backup reciente.
3. Confirmar Safe Mode segun alcance del piloto.
4. Confirmar app, PostgreSQL, worker, monitor y storage saludables.
5. Confirmar responsables operativos y ventana de soporte.

## Inicio

- Registrar hora de inicio.
- Validar login y permisos.
- Validar evento activo.
- Validar canales de comunicacion autorizados.
- Confirmar monitoreo y logs.

## Monitoreo

- Salud de app.
- PostgreSQL.
- Worker y jobs.
- Storage.
- Auditoria.
- Comunicaciones.
- Aislamiento por evento y organizacion.

## Cierre

- Generar backup.
- Registrar metricas.
- Revisar auditoria.
- Confirmar jobs pendientes.
- Documentar incidentes.

## Suspension Inmediata

Suspender si ocurre:

- Perdida de aislamiento.
- Errores generalizados de autenticacion.
- Corrupcion de datos.
- Jobs duplicados.
- Envios externos inesperados.
- Caida persistente.
- Error de storage.
- Error de restore.
- Recursos fuera de rango.
- Fallo de auditoria.
- Inconsistencia de permisos.

## Recuperacion

Usar `DISASTER_RECOVERY_RUNBOOK.md` y restaurar desde backup certificado.
